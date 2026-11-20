"""Checks for roomnoise.py on synthetic signals (the speech detector is replaced by a loudness rule).   python tests/test_roomnoise.py"""
import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import roomnoise  # noqa: E402
import spectra_prep  # noqa: E402

SR = 16000
FR = 512


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        sys.exit(1)


def fake_probs(x):
    n = len(x) // FR
    rms = np.sqrt(np.mean(x[: n * FR].reshape(n, FR) ** 2, axis=1))
    return (rms > 0.02).astype(np.float32)


spectra_prep.speech_probs = fake_probs
rng = np.random.default_rng(3)


def speech(seconds):
    t = np.arange(int(seconds * SR)) / SR
    return (0.2 * np.sin(2 * np.pi * 150 * t) * (0.7 + 0.3 * np.sin(2 * np.pi * 4 * t))).astype(np.float32)


def band(x, lo, hi):
    spec = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return spec[(f >= lo) & (f < hi)].sum()


# A recording: 1 s of low-pass room noise, 3 s of speech over that noise, 1 s of noise. Noise is mostly below 1 kHz.
sos = butter(4, 800, btype="low", output="sos", fs=SR)
noise = sosfilt(sos, rng.standard_normal(5 * SR)).astype(np.float32)
noise *= 0.004 / np.sqrt(np.mean(noise ** 2))
original = noise.copy()
original[SR: 4 * SR] += speech(3.0)
room = roomnoise.measure(original)
check(room is not None, "a recording with a quiet lead-in can be measured")
true_snr = 20 * np.log10(np.sqrt(np.mean(speech(3.0) ** 2)) / 0.004)
check(abs(room["snr_db"] - true_snr) < 3, f"its SNR is found ({room['snr_db']:.1f} dB, true {true_snr:.1f})")
check(abs(room["noise_rms"] - 0.004) < 0.001, f"its noise level is found ({room['noise_rms']:.4f}, true 0.004)")

clone = np.zeros(4 * SR, np.float32)
clone[SR // 2: SR // 2 + 3 * SR] = speech(3.0)
noisy = roomnoise.add_to(clone, room, seed=1)
check(len(noisy) == len(clone) and noisy.dtype == np.float32, "same length as the clone")
gap = noisy[: SR // 2 - 2000]
check(abs(np.sqrt(np.mean(gap ** 2)) - 0.004) < 0.0012, f"the gaps now hold noise at the original's level ({np.sqrt(np.mean(gap ** 2)):.4f})")
check(band(gap, 0, 1000) > 20 * band(gap, 2000, 8000), "and it has the original's shape: low-frequency, not white")
again = roomnoise.add_to(clone, room, seed=1)
other = roomnoise.add_to(clone, room, seed=2)
check(np.array_equal(noisy, again) and not np.array_equal(noisy, other), "the same seed gives the same noise, another seed a different one")
check(np.array_equal(clone[SR // 2: SR // 2 + 3 * SR], speech(3.0)), "the input clone was not changed")
check(roomnoise.add_to(clone, None) is clone, "no room measured: the clone is returned as it was")

check(roomnoise.measure(np.zeros(3 * SR, np.float32)) is None, "silence cannot be measured")
config.ROOM_NOISE_SNR_RANGE = (10.0, 20.0)
check(roomnoise.add_to(clone, {**room, "snr_db": 3.0}, seed=1) is clone, "an SNR below the range is not trusted: nothing is added")
quiet = roomnoise.add_to(clone, {**room, "snr_db": 60.0}, seed=1)
expected = np.sqrt(np.mean(speech(3.0) ** 2)) / 10 ** (20 / 20)
check(abs(np.sqrt(np.mean(quiet[: SR // 2 - 2000] ** 2)) / expected - 1) < 0.25, "an SNR above the range is held to the top of it (20 dB)")

# A recording whose pauses are exact digital silence (browser noise gate) has no room noise to copy
gated = original.copy()
gated[: SR] = 0
gated[4 * SR:] = 0
check(roomnoise.measure(gated) is None, "pauses of exact digital silence are not taken for room noise")
print("ALL PASSED")
