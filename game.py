"""The listening game for one session: shuffled neutral cards, the pick, and the reveal.
The browser only ever gets random card ids. Which card is real, and which engine made each clone, stays in meta.json until the pick."""
import io
import secrets
import random

import numpy as np
import soundfile as sf

import audio
import config
import scoring
import store


def _clip_path(sid: str, entry: dict):
    d = store.path(sid)
    return d / ("original.wav" if entry["kind"] == "real" else f"clones/{entry['slot']}.wav")


def make_cards(sid: str) -> list[str]:
    """Create (once) the shuffled cards for this session and return their ids in display order."""
    def build(m):
        if "cards" in m:
            return
        cards = [{"id": secrets.token_urlsafe(6), "kind": "real", "engine": None, "slot": None}]
        for name, v in m["engines"].items():
            if v["status"] == "done":
                cards.append({"id": secrets.token_urlsafe(6), "kind": "clone", "engine": name, "slot": v["slot"]})
        random.SystemRandom().shuffle(cards)
        m["cards"] = cards
    meta = store.update_meta(sid, build)
    return [c["id"] for c in meta["cards"]]


def find_card(sid: str, card_id: str) -> dict | None:
    for c in store.read(sid, "meta.json", {}).get("cards", []):
        if c["id"] == card_id:
            return c
    return None


def playback_wav(sid: str, card: dict) -> bytes:
    """What the participant hears: same format, same loudness, same lead and tail silence for every card."""
    x, sr = sf.read(str(_clip_path(sid, card)), dtype="float32")
    x = audio.to_16k(x if x.ndim == 1 else x.mean(axis=1), sr)
    frame = 320                                                  # 20 ms
    n = len(x) // frame
    if n > 4:
        env = np.sqrt(np.mean(x[: n * frame].reshape(n, frame) ** 2, axis=1))
        live = np.flatnonzero(env > 0.05 * env.max())
        pad = int(config.PLAY_PAD_SECONDS * audio.SR)
        x = x[max(0, live[0] * frame - pad): min(len(x), (live[-1] + 1) * frame + pad)]
    rms = float(np.sqrt(np.mean(x ** 2))) + 1e-9
    gain = 10 ** (config.PLAY_TARGET_RMS_DBFS / 20) / rms
    peak = float(np.max(np.abs(x))) + 1e-9
    x = x * min(gain, 0.95 / peak)
    buf = io.BytesIO()
    sf.write(buf, x, audio.SR, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def pick(sid: str, card_id: str) -> dict:
    """Record the participant's pick (the first one stands) and return the reveal."""
    def fn(m):
        if "pick" not in m:
            m["pick"] = card_id
    meta = store.update_meta(sid, fn)
    return reveal(sid, meta)


def reveal(sid: str, meta: dict | None = None) -> dict:
    meta = meta or store.read(sid, "meta.json", {})
    out = []
    for c in meta["cards"]:
        x, sr = sf.read(str(_clip_path(sid, c)), dtype="float32")
        m = round(scoring.margin(x if x.ndim == 1 else x.mean(axis=1)), 1)
        out.append({"card": c["id"], "real": c["kind"] == "real", "who": "You" if c["kind"] == "real" else config.ENGINE_LABELS.get(c["engine"], c["engine"]),
                    "margin": m, "says_clone": m < config.CUTOFF, "seconds": round(len(x) / sr, 1)})
    picked = next(r for r in out if r["card"] == meta["pick"])
    # Cache the scores with the session: they are what a training run would want next to the audio.
    store.update_meta(sid, lambda mm: mm.update(scores={r["card"]: r["margin"] for r in out}, cutoff=config.CUTOFF))
    return {"won": picked["real"], "picked": meta["pick"], "cutoff": config.CUTOFF, "cards": out}
