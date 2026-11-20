"""Give a clone the room it would have been recorded in, for PLAYBACK ONLY.

The clones come out of the engines studio-clean while the participant's own recording has room noise in it, which is a
giveaway to the ear. The clone check (Spectra) is run on the clean clone, as before. Only the clip people listen to gets the noise.

How: the quiet stretches of the participant's recording (found with the Silero speech detector) give the shape of the room noise
(its spectrum) and how loud it is next to the speech (its SNR). Fresh noise with that spectrum is made for the whole length of
the clone and mixed in at the same SNR. Nothing is looped, so there is no repeat to hear. If the recording has too little quiet
to measure, the clone is returned unchanged.
"""
import numpy as np
from scipy.signal import fftconvolve

import config
import spectra_prep

_FRAME = 512                 # the Silero frame (32 ms at 16 kHz)
_NFFT = 512
_MIN_NOISE_FRAMES = 6        # about 0.2 s of usable quiet


def _frames(x: np.ndarray, probs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = len(probs)
    return x[: n * _FRAME].reshape(n, _FRAME), np.arange(n)


def measure(original: np.ndarray) -> dict | None:
    """Room noise of a recording: {"fir": filter shaping white noise like it, "noise_rms", "speech_rms", "snr_db"}, or None if it cannot be measured."""
    x = original.astype(np.float32)
    probs = spectra_prep.speech_probs(x)
    n = len(probs)
    if n < 20:
        return None
    frames, idx = _frames(x, probs)
    voiced = probs >= 0.5
    if voiced.sum() < 10:
        return None
    near_speech = np.zeros(n, bool)                      # keep 3 frames (100 ms) away from speech: breaths and word edges are not room noise
    for i in np.flatnonzero(voiced):
        near_speech[max(0, i - 3): i + 4] = True
    energy = np.mean(frames ** 2, axis=1)
    live = energy > 1e-10                                # browsers often gate the pauses to exact digital silence (-100 dBFS or lower): that is not room noise
    quiet = (probs < 0.2) & ~near_speech & live
    quiet[:3] = False                                    # the click as the microphone opens
    if quiet.sum() < _MIN_NOISE_FRAMES:                  # a recording with no clean lead-in: take the quietest tenth of what has any noise in it
        order = np.argsort(np.where(live & ~voiced, energy, np.inf))
        quiet = np.zeros(n, bool)
        quiet[order[: max(_MIN_NOISE_FRAMES, n // 10)]] = True
        quiet &= live & ~voiced
        if quiet.sum() < _MIN_NOISE_FRAMES:
            return None
    nz = frames[quiet]
    # Medians, not means: a thump (the microphone being handled, the click of the stop button) lands in the quiet frames too and would make the
    # room sound much louder than the hiss people actually hear. For steady noise the median of a frame's power equals its mean.
    noise_rms = float(np.sqrt(np.median(np.mean(nz ** 2, axis=1))))
    speech_rms = float(np.sqrt(np.mean(frames[voiced] ** 2)))
    if noise_rms <= 1e-6 or speech_rms <= 0:
        return None
    win = np.hanning(_FRAME + 1)[:-1]
    power = np.median(np.abs(np.fft.rfft(nz * win, n=_NFFT, axis=1)) ** 2, axis=0) / np.log(2)   # the median of a periodogram bin is ln 2 times its mean
    power = np.convolve(np.pad(power, 2, mode="edge"), np.ones(5) / 5, mode="valid")     # light smoothing: shape of the noise, not its exact bins
    mag = np.sqrt(power)
    fir = np.fft.fftshift(np.fft.irfft(mag, n=_NFFT)) * np.hanning(_NFFT)                 # zero-phase filter with that magnitude
    fir = (fir / (np.sqrt(np.sum(fir ** 2)) + 1e-12)).astype(np.float32)                  # unit gain: white noise in, unit-RMS noise out
    return {"fir": fir, "noise_rms": noise_rms, "speech_rms": speech_rms, "snr_db": float(20 * np.log10(speech_rms / noise_rms))}


def add_to(clone: np.ndarray, room: dict | None, seed: int | None = None) -> np.ndarray:
    """The clone with that room's noise mixed in at the room's SNR (against the clone's own speech level). Same length as the clone."""
    if not room or len(clone) < 4 * _FRAME:
        return clone
    x = clone.astype(np.float32)
    probs = spectra_prep.speech_probs(x)
    voiced = probs >= 0.5
    if voiced.sum() < 5:
        return clone
    frames, _ = _frames(x, probs)
    speech_rms = float(np.sqrt(np.mean(frames[voiced] ** 2)))
    low, high = config.ROOM_NOISE_SNR_RANGE
    if room["snr_db"] < low:        # a recording that noisy would not have passed the quality check: the measurement is wrong (loud non-speech taken for quiet), so add nothing
        return clone
    snr = min(room["snr_db"], high)
    target_rms = speech_rms / (10 ** (snr / 20))
    rng = np.random.default_rng(seed)
    white = rng.standard_normal(len(x) + len(room["fir"])).astype(np.float32)
    shaped = fftconvolve(white, room["fir"], mode="same")[: len(x)].astype(np.float32)
    shaped *= target_rms / (float(np.sqrt(np.mean(shaped ** 2))) + 1e-12)
    return x + shaped
