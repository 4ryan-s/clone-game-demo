"""Makes the clones for one session: every enabled engine runs at the same time on the participant's recording.
Slots are neutral ids ("c1", "c2", ...) so nothing sent to the browser names an engine."""
import contextlib
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
# The local GPU worker handles one clone at a time; two participants at once would queue here instead of timing out.
_locks = {"cosyvoice": threading.Lock(), "qwen3tts": threading.Lock()}


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
        with _locks.get(eng.name, contextlib.nullcontext()):
            info = eng.clone(d / "original.wav", text, text, raw)
        x, sr = audio.read_wav_bytes(raw.read_bytes())
        (d / "clones").mkdir(exist_ok=True)
        audio.write_wav(d / "clones" / f"{slot}.wav", audio.to_16k(x, sr))
        result = {"status": "done", "seconds": round(time.time() - t0, 2), "error": None, "source_sample_rate": sr, **(info or {})}
    except Exception as exc:  # noqa: BLE001
        log.warning("engine %s failed for %s: %s", eng.name, sid, exc)
        result = {"status": "error", "seconds": round(time.time() - t0, 2), "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    store.update_meta(sid, lambda m: m["engines"][eng.name].update(result))


def _run(sid: str, ens, slots) -> None:
    text = config.SENTENCE
    with ThreadPoolExecutor(max_workers=len(ens)) as pool:
        list(pool.map(lambda e: _one(sid, e, slots[e.name], text), ens))

    def fin(m):
        m["state"] = "done" if all(v["status"] == "done" for v in m["engines"].values()) else "error"
        m["finished_at"] = time.time()
    store.update_meta(sid, fin)
