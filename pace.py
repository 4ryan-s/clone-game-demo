"""Make a clone speak at the speed of the participant's own recording.

Both clips say the same words (the clone speaks what speech to text heard), so the time from the first to the last speech
frame says how fast each was spoken. Sarvam is asked for a corrected `pace` inside its engine. Qwen3-TTS has no speed setting
and tends to speak 5 to 25 % faster than the person, so any clone that is off by more than config.PACE_TOLERANCE is
time-stretched here. The stretch keeps the pitch (WSOLA: overlapping frames are re-spaced, nothing is resampled).
"""
import numpy as np

import config
import spectra_prep

_WIN = 640          # 40 ms at 16 kHz
_TOL = 160          # how far (10 ms) a frame may move to line up with the one before it
_SANE = (0.5, 2.0)  # a clone this far off its target is broken (a run-on, or cut off): leave it alone


def stretch(x: np.ndarray, factor: float) -> np.ndarray:
    """Return x lasting `factor` times as long (above 1 = slower), same pitch. 16 kHz mono float32."""
    x = np.asarray(x, dtype=np.float32)
    if abs(factor - 1.0) < 1e-3 or len(x) < 4 * _WIN:
        return x
    hs = _WIN // 2                              # synthesis hop
    ha = hs / factor                            # analysis hop
    pad = _WIN + _TOL
    xp = np.concatenate([np.zeros(pad, np.float32), x, np.zeros(pad + _WIN, np.float32)])
    win = np.hanning(_WIN + 1)[:-1].astype(np.float32)          # periodic Hann: overlaps of 50 % add up to 1
    n_frames = int(np.ceil(len(x) * factor / hs)) + 1
    out = np.zeros(n_frames * hs + _WIN, np.float32)
    prev = None
    for k in range(n_frames):
        target = pad + int(round(k * ha))
        target = min(target, len(xp) - _WIN - 1)
        if prev is None:
            start = target
        else:
            natural = xp[prev + hs: prev + hs + _WIN]           # what would have followed the previous frame
            lo, hi = max(0, target - _TOL), min(len(xp) - _WIN, target + _TOL)
            seg = xp[lo: hi + _WIN]
            corr = np.correlate(seg, natural, mode="valid")
            energy = np.sqrt(np.convolve(seg ** 2, np.ones(_WIN, np.float32), mode="valid") + 1e-9)
            start = lo + int(np.argmax(corr / energy))
        out[k * hs: k * hs + _WIN] += xp[start: start + _WIN] * win
        prev = start
    out = out[: int(len(x) * factor)]
    return out.astype(np.float32)


def speech_seconds(x: np.ndarray) -> float:
    return spectra_prep.speech_span(x.astype(np.float32))


def match_speed(clone: np.ndarray, original: np.ndarray) -> tuple[np.ndarray, dict]:
    """The clone, stretched to last as long as the original's speech (times config.CLONE_SLOWDOWN). Returns (audio, info).
    Left alone when it is already within the tolerance, or so far off (a run-on or a clipped clone) that stretching would not fix it."""
    target = speech_seconds(original) * config.CLONE_SLOWDOWN
    got = speech_seconds(clone)
    info = {"speed_target_s": round(target, 2), "speed_before_s": round(got, 2), "speed_stretch": 1.0}
    if target <= 0 or got <= 0:
        return clone, info
    factor = target / got
    if abs(factor - 1.0) <= config.PACE_TOLERANCE or not (_SANE[0] <= factor <= _SANE[1]):
        return clone, info
    lo, hi = config.PACE_STRETCH_LIMITS
    factor = min(hi, max(lo, factor))            # a big stretch is audible: go as far as the limit, not further
    out = stretch(clone, factor)
    info.update(speed_stretch=round(factor, 3), speed_after_s=round(speech_seconds(out), 2))
    return out, info
