"""Micro-batching: several requests that arrive close together are run through the model as ONE batch.

Why: generating speech one clip at a time leaves the GPU mostly idle (it waits on the Python loop between tiny steps), so
four clips in one batch take about as long as one clip. A single worker with one model copy can therefore serve several
people at once, instead of making them queue or needing several model copies.

How it works:
  1. Every request calls submit() and waits.
  2. One background thread takes the first waiting request, then keeps collecting more for a short window (window_s,
     or until max_batch requests are in hand), then runs them all with a single call to run_batch().
  3. Each request gets back its own result.
A request that arrives while a batch is running waits for the next batch (a batch is not extended once it has started).
A lone request is delayed by at most window_s, then runs on its own.
If a batch fails as a whole, its requests are retried one at a time, so one bad request does not fail the others.

This module knows nothing about the model: run_batch(payloads) -> list of results (a dict, or an Exception for that one request).
"""
import logging
import queue
import threading
import time

log = logging.getLogger("batcher")


class _Job:
    __slots__ = ("payload", "done", "result", "error", "queued_at", "meta")

    def __init__(self, payload):
        self.payload = payload
        self.done = threading.Event()
        self.result = None
        self.error = None
        self.queued_at = time.monotonic()
        self.meta = {}


class Batcher:
    def __init__(self, run_batch, max_batch: int = 4, window_s: float = 2.0):
        self._run_batch = run_batch
        self.max_batch = max(1, int(max_batch))
        self.window_s = max(0.0, float(window_s))
        self._queue: "queue.Queue[_Job]" = queue.Queue()
        self._lock = threading.Lock()
        self._batch_no = 0
        self.stats = {"batches": 0, "jobs": 0, "last_batch": 0, "largest_batch": 0, "running": 0}
        threading.Thread(target=self._loop, name="batcher", daemon=True).start()

    # ------------------------------------------------------------ public
    def submit(self, payload, timeout: float | None = None):
        """Queue one request and wait for its result. Raises the request's own error, or TimeoutError."""
        job = _Job(payload)
        self._queue.put(job)
        if not job.done.wait(timeout):
            raise TimeoutError("the request waited too long for its batch")
        if job.error is not None:
            raise job.error
        return job.result

    def snapshot(self) -> dict:
        with self._lock:
            s = dict(self.stats)
        return {**s, "waiting": self._queue.qsize(), "max_batch": self.max_batch, "window_s": self.window_s}

    # ------------------------------------------------------------ internals
    def _loop(self):
        while True:
            batch = [self._queue.get()]
            deadline = time.monotonic() + self.window_s
            reason = "full"
            while len(batch) < self.max_batch:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    reason = "window expired"
                    break
                try:
                    batch.append(self._queue.get(timeout=remaining))
                except queue.Empty:
                    reason = "window expired"
                    break
            self._execute(batch, reason)

    def _execute(self, batch, reason="full"):
        with self._lock:
            self.stats["running"] = len(batch)
            self._batch_no += 1
            no = self._batch_no
        start = time.monotonic()
        waits = [start - j.queued_at for j in batch]
        log.info("batch #%d start: %d request(s) (%s, max %d), still queued %d, waited %s",
                 no, len(batch), reason, self.max_batch, self._queue.qsize(), ", ".join("%.1fs" % w for w in waits))
        for j, w in zip(batch, waits):
            j.meta = {"batch_id": no, "queue_wait_s": round(w, 2), "batch_reason": reason}
        try:
            self._run(batch)
        finally:
            log.info("batch #%d finished in %.1fs", no, time.monotonic() - start)
            with self._lock:
                self.stats["batches"] += 1
                self.stats["jobs"] += len(batch)
                self.stats["last_batch"] = len(batch)
                self.stats["largest_batch"] = max(self.stats["largest_batch"], len(batch))
                self.stats["running"] = 0

    def _run(self, batch):
        try:
            results = self._run_batch([j.payload for j in batch])
            if len(results) != len(batch):
                raise RuntimeError(f"run_batch returned {len(results)} results for {len(batch)} requests")
        except Exception as exc:  # noqa: BLE001
            if len(batch) == 1:
                self._finish(batch[0], exc)
                return
            log.warning("batch of %d failed (%s: %s): retrying the requests one at a time", len(batch), type(exc).__name__, str(exc)[:150])
            for job in batch:                       # retry one at a time: only the request that is really bad fails
                try:
                    self._finish(job, self._run_batch([job.payload])[0])
                except Exception as single_exc:  # noqa: BLE001
                    self._finish(job, single_exc)
            return
        for job, result in zip(batch, results):
            self._finish(job, result)

    @staticmethod
    def _finish(job: _Job, result):
        if isinstance(result, BaseException):
            job.error = result
        else:
            if isinstance(result, dict):
                result.update(job.meta)
            job.result = result
        job.done.set()
