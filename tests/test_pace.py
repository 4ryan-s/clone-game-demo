"""Checks for pace.py (time-stretch and speed matching) on synthetic signals.   python tests/test_pace.py"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import pace  # noqa: E402

SR = 16000


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        sys.exit(1)


def voice_like(seconds, f0=140.0):
    """A pitch with harmonics and a slow wobble in loudness, a bit like speech."""
    t = np.arange(int(seconds * SR)) / SR
    x = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 8))
    return (x * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t)) * 0.2).astype(np.float32)


def peak_hz(x):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return np.argmax(spec[20:2000]) * SR / len(x) + 20 * SR / len(x)


x = voice_like(3.0)
for factor in (0.8, 0.9, 1.1, 1.25):
    y = pace.stretch(x, factor)
    check(abs(len(y) / len(x) - factor) < 0.01, f"stretch x{factor}: length changes by that factor ({len(y) / len(x):.3f})")
    check(abs(peak_hz(y) - peak_hz(x)) / peak_hz(x) < 0.03, f"stretch x{factor}: pitch is kept ({peak_hz(x):.0f} Hz -> {peak_hz(y):.0f} Hz)")
    check(0.7 < np.sqrt(np.mean(y ** 2)) / np.sqrt(np.mean(x ** 2)) < 1.3, f"stretch x{factor}: loudness is kept")
check(np.array_equal(pace.stretch(x, 1.0), x), "stretch x1.0 returns the clip untouched")
check(not np.isnan(pace.stretch(x, 1.2)).any(), "no NaN in the output")

# match_speed, with the speech detector replaced by the clip length (every clip here is "all speech")
pace.speech_seconds = lambda a: len(a) / SR
orig = voice_like(5.0)
config.CLONE_SLOWDOWN = 1.0
out, info = pace.match_speed(voice_like(4.0), orig)
check(abs(len(out) / SR - 5.0) < 0.1 and info["speed_stretch"] > 1.2, f"a clone 20 % too fast is slowed to the original's length ({len(out) / SR:.2f} s, x{info['speed_stretch']})")
out, info = pace.match_speed(voice_like(4.9), orig)
check(len(out) == len(voice_like(4.9)) and info["speed_stretch"] == 1.0, "a clone within the tolerance is left alone")
out, info = pace.match_speed(voice_like(3.0), orig)
check(abs(len(out) / SR - 3.0 * config.PACE_STRETCH_LIMITS[1]) < 0.1, f"a big difference is stretched only as far as the limit ({len(out) / SR:.2f} s)")
out, info = pace.match_speed(voice_like(14.0), orig)
check(info["speed_stretch"] == 1.0 and len(out) == 14 * SR, "a run-on clone (far too long) is left alone")
config.CLONE_SLOWDOWN = 1.1
out, info = pace.match_speed(voice_like(5.0), orig)
check(abs(len(out) / SR - 5.5) < 0.1, f"CLONE_SLOWDOWN 1.1 makes it 10 % slower than the original ({len(out) / SR:.2f} s)")
print("ALL PASSED")
