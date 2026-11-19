"""Audio helpers: read what the browser sent, judge whether it is a usable recording, write 16 kHz mono WAV."""
import io
from math import gcd

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

import config

SR = 16000


def read_wav_bytes(data: bytes) -> tuple[np.ndarray, int]:
    """Decode WAV bytes into mono float32 plus the file's sample rate. Raises ValueError for anything else."""
    try:
        x, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("The recording is not a readable WAV file") from exc
    return x.mean(axis=1), sr


def to_16k(x: np.ndarray, sr: int) -> np.ndarray:
    if sr == SR:
        return np.ascontiguousarray(x, dtype=np.float32)
    g = gcd(sr, SR)
    return resample_poly(x, SR // g, sr // g).astype(np.float32)


def to_wav_bytes(x: np.ndarray, sr: int = SR) -> bytes:
    """The clip as 16-bit mono WAV bytes (for sending to speech to text without writing a file)."""
    buf = io.BytesIO()
    sf.write(buf, np.clip(x, -1.0, 1.0), sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def write_wav(path, x: np.ndarray, sr: int = SR) -> None:
    sf.write(str(path), np.clip(x, -1.0, 1.0), sr, subtype="PCM_16")


def check_recording(x: np.ndarray) -> dict:
    """Quality gate for the participant's recording. `issues` are plain sentences safe to show on screen."""
    dur = len(x) / SR
    rms = float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0
    rms_db = 20 * np.log10(rms + 1e-9)
    clipped = float(np.mean(np.abs(x) >= 0.999)) if len(x) else 0.0
    issues = []
    if dur < config.MIN_SECONDS:
        issues.append(f"That was too short ({dur:.1f} s). Please read the whole sentence.")
    if dur > config.MAX_SECONDS:
        issues.append(f"That was too long ({dur:.1f} s). Please read just the sentence.")
    if rms_db < config.MIN_RMS_DBFS:
        issues.append("That was too quiet. Move closer to the microphone and try again.")
    if clipped > config.MAX_CLIPPED_FRACTION:
        issues.append("That was too loud and distorted. Move back a little and try again.")
    return {"ok": not issues, "seconds": round(dur, 2), "level_dbfs": round(rms_db, 1), "clipped_fraction": round(clipped, 4), "issues": issues}
