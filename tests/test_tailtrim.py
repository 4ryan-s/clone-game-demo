"""Checks tailtrim.py.   python tests/test_tailtrim.py <speech.wav>     (a 16 kHz mono recording of someone speaking, 3 s or more)"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tailtrim  # noqa: E402


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        sys.exit(1)


x, sr = sf.read(sys.argv[1], dtype="float32")
x = x if x.ndim == 1 else x.mean(axis=1)
assert sr == 16000, "use a 16 kHz clip"
clean, base = tailtrim.trim_tail(x, sr)
speech_end = base["speech_end"]
check(base["tail_s"] < 1.5, f"a normal clip keeps (almost) all of its length ({base['total']} s, speech ends {speech_end} s)")

# what Qwen does: loud tonal noise for 5 s after the sentence, about 7 dB under the speech level
level = float(np.sqrt(np.mean(x[: int(speech_end * sr)] ** 2)))
t = np.arange(5 * sr) / sr
hum = (0.45 * level * (np.sin(2 * np.pi * 110 * t) + 0.5 * np.sin(2 * np.pi * 220 * t)) / 1.5).astype(np.float32)
long = np.concatenate([x[: int(speech_end * sr)], hum])
out, info = tailtrim.trim_tail(long, sr, cap_s=len(long) / sr)
check(info["trimmed_s"] > 4.3, f"a 5 s tonal tail is cut off ({info['trimmed_s']} s removed)")
check(abs(len(out) / sr - (speech_end + 0.3)) < 0.15, f"the clip now ends 0.3 s after the speech ({len(out) / sr:.2f} s, speech ended {speech_end} s)")
check(np.allclose(out[: int((speech_end - 0.1) * sr)], long[: int((speech_end - 0.1) * sr)]), "the speech itself is untouched")
check(abs(out[-1]) < 1e-3, "the cut ends with a short fade, so there is no click")
check(not info["ran_on"], "a clip that stopped by itself is not flagged as running on")

# still speaking when the cap is reached: flagged so it can be generated again
_o, info2 = tailtrim.trim_tail(x, sr, cap_s=len(x) / sr)
check(info2["ran_on"] == (info2["speech_end"] >= info2["total"] - 0.5), "running on is flagged only when the speech reaches the end at the cap")
speech_to_the_end = x[: int(speech_end * sr)]
_o, info3 = tailtrim.trim_tail(speech_to_the_end, sr, cap_s=len(speech_to_the_end) / sr)
check(info3["ran_on"], "speech that is still going at the cap is flagged to be generated again")
_o, info4 = tailtrim.trim_tail(np.zeros(3 * sr, dtype=np.float32), sr)
check(info4.get("no_speech") and info4["trimmed_s"] == 0.0, "a clip with no speech is left alone")
print("ALL PASSED")
