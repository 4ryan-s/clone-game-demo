"""Makes the clones for one session: every enabled engine runs at the same time on the participant's recording.
Slots are neutral ids ("c1", "c2", ...) so nothing sent to the browser names an engine."""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import audio
import config
import engines
import pace
import store
from engines.base import EngineError

log = logging.getLogger("pipeline")
# Engines that must not run at the same time hold a shared lock, keyed by eng.lock_key:
#   - Qwen is NOT locked (serialize = False): its workers batch simultaneous requests and the engine spreads them over the workers.
#   - "sarvam":   both Sarvam clones share one remote rate limit, so they go one after another, not together.
_locks: dict[str, threading.Semaphore] = {}
_locks_guard = threading.Lock()


def _lock_for(eng) -> threading.Semaphore:
    """A semaphore per lock group: max_concurrent = 1 behaves like a lock; Sarvam allows a few at once."""
    with _locks_guard:
        return _locks.setdefault(eng.lock_key, threading.Semaphore(max(1, eng.max_concurrent)))


def start(sid: str) -> None:
    """Kick off generation in the background. Safe to call once per recording."""
    ens = engines.enabled()
    slots = {e.name: f"c{i}" for i, e in enumerate(ens, 1)}

    def init(m):
        m["state"] = "running"
        m["started_at"] = time.time()
        m["engines"] = {n: {"slot": s, "status": "running", "seconds": None, "error": None} for n, s in slots.items()}
    store.update_meta(sid, init)
    log.info("session %s generating with %d engines: %s", sid, len(ens), ", ".join(e.name for e in ens))
    threading.Thread(target=_run, args=(sid, ens, slots), daemon=True).start()


def _one(sid: str, eng, slot: str, text: str) -> None:
    d = store.path(sid)
    t0 = time.time()
    try:
        ok, why = eng.available()
        if not ok:
            raise EngineError(why)
        raw = d / "raw" / f"{eng.name}.wav"
        if eng.serialize:
            with _lock_for(eng):
                info = eng.clone(d / "original.wav", text, text, raw)
        else:
            info = eng.clone(d / "original.wav", text, text, raw)
        x, sr = audio.read_wav_bytes(raw.read_bytes())
        raw.unlink(missing_ok=True)   # the engine's file is not kept; only the playback clip remains, and only until the session ends
        (d / "clones").mkdir(exist_ok=True)
        x16 = audio.to_16k(x, sr)
        speed = {}
        try:   # speak at the participant's speed (pace.py). An extra: never lose the clone because it failed.
            ox, osr = audio.read_wav_bytes((d / "original.wav").read_bytes())
            x16, speed = pace.match_speed(x16, audio.to_16k(ox, osr))
        except Exception as exc:  # noqa: BLE001
            speed = {"speed_error": f"{type(exc).__name__}: {str(exc)[:100]}"}
        audio.write_wav(d / "clones" / f"{slot}.wav", x16)     # clean: this exact file is what the clone check scores
        log.debug("session %s engine %s done in %.1fs", sid, eng.name, time.time() - t0)
        result = {"status": "done", "seconds": round(time.time() - t0, 2), "error": None, "source_sample_rate": sr, **(info or {}), **speed}
    except Exception as exc:  # noqa: BLE001
        log.warning("session %s engine %s FAILED after %.1fs: %s: %s", sid, eng.name, time.time() - t0, type(exc).__name__, str(exc)[:300])
        result = {"status": "error", "seconds": round(time.time() - t0, 2), "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    store.update_meta(sid, lambda m: m["engines"][eng.name].update(result))


def _run(sid: str, ens, slots) -> None:
    # Whatever the participant said (from speech to text) is what every clone says, and it is also the transcript of the
    # reference audio. Qwen3-TTS needs that transcript to match the audio exactly: with the wrong one it produced
    # unintelligible speech in our test. If speech to text was unavailable, fall back to the sentence shown on screen.
    heard = (store.read(sid, "recording.json", {}).get("transcript") or "").strip()
    text = heard or config.SENTENCE
    if not heard:
        log.warning("session %s has no transcript: the clones will say the sentence on screen instead of what was recorded (Qwen may sound wrong)", sid)
    with ThreadPoolExecutor(max_workers=len(ens)) as pool:
        list(pool.map(lambda e: _one(sid, e, slots[e.name], text), ens))

    def fin(m):
        m["state"] = "done" if all(v["status"] == "done" for v in m["engines"].values()) else "error"
        m["finished_at"] = time.time()
    meta = store.update_meta(sid, fin)
    parts = []
    for name, v in meta["engines"].items():
        part = f"{name}={v['status']} in {v['seconds']}s"
        if v["status"] != "done":
            part += f" ({str(v['error'])[:80]})"
        elif v.get("worker"):
            part += f" [worker {v['worker']}, batch of {v.get('batch_size')}, waited {v.get('queue_wait_s')}s for the batch, generation {v.get('generation_s')}s]"
        parts.append(part)
    log.info("session %s clones %s in %.1fs: %s", sid, meta["state"].upper(), meta["finished_at"] - meta["started_at"], "; ".join(parts))
