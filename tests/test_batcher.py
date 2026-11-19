"""Checks workers/batcher.py with a fake model (no GPU).   python tests/test_batcher.py"""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from workers.batcher import Batcher  # noqa: E402


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        sys.exit(1)


def make(run_time=0.2, fail_if=None, **kw):
    calls = []

    def run(jobs):
        calls.append([j["id"] for j in jobs])
        time.sleep(run_time)
        if fail_if and any(fail_if(j) for j in jobs) and len(jobs) > 1:
            raise RuntimeError("batch failed")
        out = []
        for j in jobs:
            out.append(ValueError(f"bad job {j['id']}") if fail_if and fail_if(j) else {"ok": True, "id": j["id"], "batch_size": len(jobs)})
        return out
    return Batcher(run, **kw), calls


def burst(b, ids, gap=0.0):
    res, errs = {}, {}

    def go(i):
        try:
            res[i] = b.submit({"id": i}, timeout=10)
        except Exception as e:  # noqa: BLE001
            errs[i] = e
    ts = [threading.Thread(target=go, args=(i,)) for i in ids]
    for t in ts:
        t.start()
        time.sleep(gap)
    [t.join() for t in ts]
    return res, errs


b, calls = make(max_batch=4, window_s=0.3)
t = time.time(); r = b.submit({"id": "solo"}, timeout=5); dt = time.time() - t
check(r["id"] == "solo" and calls == [["solo"]], "a lone request runs on its own")
check(dt < 0.3 + 0.2 + 0.3, f"a lone request is delayed only by the short window ({dt:.2f} s for a 0.2 s job)")

b, calls = make(max_batch=4, window_s=0.3)
res, errs = burst(b, [1, 2, 3, 4], gap=0.02)
check(len(calls) == 1 and sorted(calls[0]) == [1, 2, 3, 4], "four requests arriving together run as ONE batch of four")
check(all(res[i]["id"] == i and res[i]["batch_size"] == 4 for i in (1, 2, 3, 4)), "each request got back its own result")

b, calls = make(max_batch=4, window_s=0.3)
res, errs = burst(b, list(range(6)), gap=0.01)
check(sorted(len(c) for c in calls) == [2, 4] and not errs, f"six requests with a limit of four become batches {sorted(len(c) for c in calls)}")
check(all(res[i]["id"] == i for i in range(6)), "all six got the right result")

b, calls = make(run_time=0.6, max_batch=4, window_s=0.2)
t1 = threading.Thread(target=lambda: b.submit({"id": "first"}, timeout=10)); t1.start()
time.sleep(0.4)                       # the first batch is now running
res, errs = burst(b, ["late1", "late2"], gap=0.01)
t1.join()
check(calls[0] == ["first"] and sorted(calls[1]) == ["late1", "late2"], "requests that arrive while a batch is running wait and share the NEXT batch")
snap = b.snapshot()
check(snap["batches"] == 2 and snap["jobs"] == 3 and snap["largest_batch"] == 2, f"stats are kept: {snap}")

b, calls = make(max_batch=4, window_s=0.3, fail_if=lambda j: j["id"] == 2)
res, errs = burst(b, [1, 2, 3], gap=0.02)
check(set(errs) == {2} and isinstance(errs[2], ValueError), "if a batch fails, only the really bad request gets the error")
check(set(res) == {1, 3} and all(res[i]["batch_size"] == 1 for i in (1, 3)), "the others are retried alone and succeed")

b, calls = make(run_time=2.0, max_batch=2, window_s=0.05)
try:
    b.submit({"id": "slow"}, timeout=0.3)
    check(False, "a request that waits too long raises TimeoutError")
except TimeoutError:
    check(True, "a request that waits too long raises TimeoutError")
print("ALL PASSED")
