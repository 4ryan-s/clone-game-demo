"""Makes the clones for one session: every enabled engine runs at the same time on the participant's recording.
Slots are neutral ids ("c1", "c2", ...) so nothing sent to the browser names an engine."""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import audio
import config
import engines
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
        audio.write_wav(d / "clones" / f"{slot}.wav", audio.to_16k(x, sr))
        log.info("session %s engine %s done in %.1fs", sid, eng.name, time.time() - t0)
        result = {"status": "done", "seconds": round(time.time() - t0, 2), "error": None, "source_sample_rate": sr, **(info or {})}
    except Exception as exc:  # noqa: BLE001
        log.warning("engine %s failed for %s: %s", eng.name, sid, exc)
        result = {"status": "error", "seconds": round(time.time() - t0, 2), "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    store.update_meta(sid, lambda m: m["engines"][eng.name].update(result))


def _run(sid: str, ens, slots) -> None:
    # Whatever the participant said (from speech to text) is what every clone says, and it is also the transcript of the
    # reference audio. Qwen3-TTS needs that transcript to match the audio exactly: with the wrong one it produced
    # unintelligible speech in our test. If speech to text was unavailable, fall back to the sentence shown on screen.
    text = (store.read(sid, "recording.json", {}).get("transcript") or "").strip() or config.SENTENCE
    with ThreadPoolExecutor(max_workers=len(ens)) as pool:
        list(pool.map(lambda e: _one(sid, e, slots[e.name], text), ens))

    def fin(m):
        m["state"] = "done" if all(v["status"] == "done" for v in m["engines"].values()) else "error"
        m["finished_at"] = time.time()
    store.update_meta(sid, fin)
