"""Cut the run-on tail off a generated clip.

Qwen3-TTS sometimes does not emit its end-of-speech token. It then keeps generating until it hits max_new_tokens, and the
clip ends with seconds of loud, tonal noise (about 7 dB below the speech level, spectral flatness near 0) after the sentence.
Measured on one test setup: default sampling ran on in 1 of 4 samples, temperature 0.7 in 2 of 4, 0.5 in 4 of 4, so lowering the
temperature makes it worse. The speech itself ends normally; only the tail is wrong, and the speech detector can find where
the speech ends, so the tail is cut there.

Worse case: the clip is still "speaking" when it hits the cap (rambling or cut mid-word). That is reported as ran_on so the
caller can generate it again.

Runs in the Qwen worker's environment: numpy, scipy and spectra_prep (Silero via onnxruntime) only."""
import numpy as np
from scipy.signal import resample_poly

import spectra_prep

_FRAME_S = 512 / 16000
FADE_S = 0.02


def trim_tail(x: np.ndarray, sr: int, pad_s: float = 0.3, cap_s: float | None = None) -> tuple[np.ndarray, dict]:
    """Return (clip cut pad_s after the last speech, info). info: total, speech_end, tail_s, trimmed_s, ran_on.
    cap_s is how long the clip could have been at most (max_new_tokens / frame rate); ran_on means the speech reaches that end."""
    x = np.asarray(x, dtype=np.float32)
    total = len(x) / sr
    x16 = x if sr == 16000 else resample_poly(x, 16000, sr).astype(np.float32)
    voiced = np.flatnonzero(spectra_prep.speech_probs(x16) >= 0.5)
    if len(voiced) == 0:
        return x, {"total": round(total, 2), "speech_end": 0.0, "tail_s": round(total, 2), "trimmed_s": 0.0, "ran_on": False, "no_speech": True}
    speech_end = (voiced[-1] + 1) * _FRAME_S
    keep = min(len(x), int(round((speech_end + pad_s) * sr)))
    out = x[:keep].copy()
    n = min(len(out), int(FADE_S * sr))
    if n > 1:
        out[-n:] *= np.linspace(1.0, 0.0, n, dtype=np.float32)
    ran_on = bool(cap_s is not None and total >= cap_s - 0.3 and speech_end >= total - 0.5)
    return out, {"total": round(total, 2), "speech_end": round(float(speech_end), 2), "tail_s": round(total - speech_end, 2),
                 "trimmed_s": round((len(x) - keep) / sr, 2), "ran_on": ran_on}
