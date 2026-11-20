"""The pipeline stretches a fast clone to the speaker's speed; the clone check scores the CLEAN clone; only playback gets room noise
and equal lead/tail.  Synthetic audio, speech detector replaced by a loudness rule, engine faked.   python tests/test_playback_realism.py"""
import io
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

config.SESSIONS_DIR = Path(tempfile.mkdtemp(prefix="realism_test_")) / "sessions"
import audio, game, pace, pipeline, roomnoise, scoring, spectra_prep, store  # noqa: E402
from engines.base import Engine  # noqa: E402

SR = 16000


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        sys.exit(1)


def fake_probs(x):
    n = len(x) // 512
    return (np.sqrt(np.mean(x[: n * 512].reshape(n, 512) ** 2, axis=1)) > 0.02).astype(np.float32)


spectra_prep.speech_probs = fake_probs
spectra_prep.speech_span = lambda x: float(np.ptp(np.flatnonzero(fake_probs(x))) + 1) * 512 / SR if fake_probs(x).any() else 0.0
rng = np.random.default_rng(5)


def speech(seconds):
    t = np.arange(int(seconds * SR)) / SR
    return (0.2 * np.sin(2 * np.pi * 150 * t) * (0.7 + 0.3 * np.sin(2 * np.pi * 4 * t))).astype(np.float32)


# The participant's recording: 1 s of low-frequency room noise, 4 s speech, 1 s noise
noise = sosfilt(butter(4, 800, btype="low", output="sos", fs=SR), rng.standard_normal(6 * SR)).astype(np.float32)
noise *= 0.004 / np.sqrt(np.mean(noise ** 2))
orig = noise.copy()
orig[SR: 5 * SR] += speech(4.0)

sid = store.new_id()
d = store.path(sid)
d.mkdir(parents=True)
audio.write_wav(d / "original.wav", orig)


class Fast(Engine):
    """A clone that says it in 3.4 s (15 % too fast) and starts at once, with no lead-in: studio clean."""
    name = "fast"

    def available(self):
        return True, ""

    def clone(self, ref_wav, ref_text, text, out_wav):
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        audio.write_wav(out_wav, speech(3.4))
        return {"service": "fake"}


store.update_meta(sid, lambda m: m.update(state="running", engines={"fast": {"slot": "c1", "status": "running"}}))
pipeline._one(sid, Fast(), "c1", "hello there")
meta = store.read(sid, "meta.json", {})
info = meta["engines"]["fast"]
check(info["status"] == "done", "the clone was made")
stored, _ = sf.read(str(d / "clones" / "c1.wav"), dtype="float32")
check(abs(len(stored) / SR - 4.0) < 0.15, f"it was stretched to the original's speech length: {len(stored) / SR:.2f} s (was 3.40, original speech 4.00)")
check(info["speed_stretch"] > 1.1, f"and the stretch is recorded in meta: x{info['speed_stretch']}")
config.PACE_TOLERANCE = 99.0            # speed matching off for one run: what is stored must then be exactly what the engine made
store.update_meta(sid, lambda m: m["engines"]["fast"].update(status="running"))
pipeline._one(sid, Fast(), "c1", "hello there")
untouched, _ = sf.read(str(d / "clones" / "c1.wav"), dtype="float32")
check(len(untouched) == len(speech(3.4)) and float(np.max(np.abs(untouched - speech(3.4)))) < 2e-4, "the stored clone is exactly the engine's clean output: no noise in it")
config.PACE_TOLERANCE = 0.05
pipeline._one(sid, Fast(), "c1", "hello there")                      # back to the stretched version for the playback checks
stored, _ = sf.read(str(d / "clones" / "c1.wav"), dtype="float32")

# playback: real card and clone card
store.update_meta(sid, lambda m: m.update(cards=[{"id": "realcard", "kind": "real", "engine": None, "slot": None},
                                                 {"id": "clonecard", "kind": "clone", "engine": "fast", "slot": "c1"}]))
def play(card):
    x, sr = sf.read(io.BytesIO(game.playback_wav(sid, card)), dtype="float32")
    return x

real, clone = play({"id": "realcard", "kind": "real"}), play({"id": "clonecard", "kind": "clone", "slot": "c1"})
pad = int(config.PLAY_PAD_SECONDS * SR)
check(abs(len(clone) - (len(stored) + 2 * pad)) < 1100 and abs(len(real) - (4 * SR + 2 * pad)) < 1100, f"both cards get the same lead and tail around the speech ({len(real) / SR:.2f} s real, {len(clone) / SR:.2f} s clone)")
lead_clone = clone[: pad - 400]
check(np.sqrt(np.mean(lead_clone ** 2)) > 1e-4, "the clone's lead-in now holds room noise (it was digital silence)")
check(abs(20 * np.log10(np.sqrt(np.mean(lead_clone ** 2)) / np.sqrt(np.mean(real[: pad - 400] ** 2)))) < 4, "at about the level of the real recording's own lead-in")

config.PLAYBACK_ROOM_NOISE = False
quiet = play({"id": "clonecard", "kind": "clone", "slot": "c1"})
check(np.sqrt(np.mean(quiet[: pad - 400] ** 2)) < 1e-5, "with PLAYBACK_ROOM_NOISE off the lead-in is clean again")
config.PLAYBACK_ROOM_NOISE = True

# the reveal scores the clean file, whatever playback does
seen = []
scoring.margin = lambda x: seen.append(np.array(x)) or 0.0
store.update_meta(sid, lambda m: m.update(pick="clonecard"))
game.reveal(sid)
clean_clone = next(s for s in seen if abs(len(s) - len(stored)) < 5)
check(np.array_equal(clean_clone, stored), "the clone check was given exactly the clean, stored clone")
print("ALL PASSED")
