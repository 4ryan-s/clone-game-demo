"""The listening game for one session: shuffled neutral cards, the pick, and the reveal.
The browser only ever gets random card ids. Which card is real, and which engine made each clone, stays in meta.json until the pick."""
import io
import logging
import secrets
import random
import zlib

import numpy as np
import soundfile as sf

import audio
import config
import roomnoise
import scoring
import spectra_prep
import stats
import store


log = logging.getLogger("game")


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


def _read16k(path) -> np.ndarray:
    x, sr = sf.read(str(path), dtype="float32")
    return audio.to_16k(x if x.ndim == 1 else x.mean(axis=1), sr)


def _trim_to_speech(x: np.ndarray) -> np.ndarray:
    """Cut every card to the same lead and tail (config.PLAY_PAD_SECONDS) around the speech. The speech detector decides where the speech is, so a
    recording with room noise is cut the same way as a clean clone (a level threshold would keep the noisy one's whole lead-in)."""
    pad = int(config.PLAY_PAD_SECONDS * audio.SR)
    try:
        voiced = np.flatnonzero(spectra_prep.speech_probs(x) >= 0.5)
    except Exception:  # noqa: BLE001
        voiced = []
    if len(voiced):
        start, end = voiced[0] * 512, (voiced[-1] + 1) * 512
    else:
        frame = 320                                              # no speech found: fall back to the 20 ms level threshold
        n = len(x) // frame
        if n <= 4:
            return x
        env = np.sqrt(np.mean(x[: n * frame].reshape(n, frame) ** 2, axis=1))
        live = np.flatnonzero(env > 0.05 * env.max())
        start, end = live[0] * frame, (live[-1] + 1) * frame
    out = x[max(0, start - pad): min(len(x), end + pad)]
    lead, tail = max(0, pad - start), max(0, end + pad - len(x))   # a clone that starts or ends right on the speech gets silence, so every card has the same lead and tail
    return np.concatenate([np.zeros(lead, np.float32), out, np.zeros(tail, np.float32)]) if lead or tail else out


def playback_wav(sid: str, card: dict) -> bytes:
    """What the participant hears: same format, same loudness, same lead and tail silence for every card."""
    x = _read16k(_clip_path(sid, card))
    x = _trim_to_speech(x)
    if card["kind"] != "real" and config.PLAYBACK_ROOM_NOISE:
        # The clone check scores the clean clone (see reveal). Only what people listen to gets the room of their own recording, so the
        # clones do not give themselves away by being studio-clean next to a recording with room noise in it.
        try:
            room = roomnoise.measure(_read16k(_clip_path(sid, {"kind": "real"})))
            x = roomnoise.add_to(x, room, seed=zlib.crc32(card["id"].encode()))
        except Exception as exc:  # noqa: BLE001   (an extra: the clean clone still plays if it fails)
            log.warning("room noise skipped for %s: %s", sid, exc)
    rms = float(np.sqrt(np.mean(x ** 2))) + 1e-9
    gain = 10 ** (config.PLAY_TARGET_RMS_DBFS / 20) / rms
    peak = float(np.max(np.abs(x))) + 1e-9
    x = x * min(gain, 0.95 / peak)
    buf = io.BytesIO()
    sf.write(buf, x, audio.SR, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def pick(sid: str, card_id: str) -> dict:
    """Record the participant's pick (the first one stands) and return the reveal."""
    first = False

    def fn(m):
        nonlocal first
        if "pick" not in m:
            m["pick"] = card_id
            first = True
    meta = store.update_meta(sid, fn)
    if first:
        cards = meta.get("cards", [])
        won = any(c["id"] == meta["pick"] and c["kind"] == "real" for c in cards)
        stats.record_attempt(won, len(cards))
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
