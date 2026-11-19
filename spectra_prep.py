"""Input preparation for the clone check, the same steps the banking login applies before Spectra-AASIST3
(window around speech with Silero VAD, pre-emphasis 0.97, pad or trim to 64600 samples). Standalone: numpy and onnxruntime only.
A parity test against the banking backend's own function is in tests/parity_prepare_wav.py."""
import threading

import numpy as np
import onnxruntime as ort

import config

PAD_INPUT_SAMPLES = 64600
PREEMPHASIS_ALPHA = 0.97
_FRAME = 512
_SPEECH_THRESHOLD = 0.5
_MARGIN = int(0.5 * 16000)
_vad_lock = threading.Lock()
_vad = None


class _Silero:
    """Silero VAD v5 (ONNX), 16 kHz, one 512-sample frame at a time with its 64-sample context."""

    def __init__(self, path):
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        self.session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"], sess_options=opts)
        self.reset()

    def reset(self):
        self.state = np.zeros((2, 1, 128), dtype="float32")
        self.context = np.zeros((1, 64), dtype="float32")

    def __call__(self, frame):
        x = np.concatenate((self.context, frame[None, :].astype("float32")), axis=1)
        out, self.state = self.session.run(None, {"input": x, "state": self.state, "sr": np.array(16000, dtype="int64")})
        self.context = x[..., -64:]
        return float(out.item())


def window_around_speech(wav: np.ndarray, target_len: int = PAD_INPUT_SAMPLES) -> np.ndarray:
    global _vad
    if len(wav) <= target_len:
        return wav
    n_frames = len(wav) // _FRAME
    try:
        with _vad_lock:
            if _vad is None:
                _vad = _Silero(config.ROOT / "assets" / "silero_vad.onnx")
            _vad.reset()
            probs = np.array([_vad(wav[i * _FRAME:(i + 1) * _FRAME]) for i in range(n_frames)])
    except Exception:  # noqa: BLE001  (same fallback as production: the head of the clip)
        return wav[:target_len]
    speech = probs >= _SPEECH_THRESHOLD
    if not speech.any():
        return wav[:target_len]
    start = max(0, int(np.argmax(speech)) * _FRAME - _MARGIN)
    end = start + target_len
    if end > len(wav):
        end = len(wav)
        start = max(0, end - target_len)
    return wav[start:end]


def speech_probs(wav: np.ndarray) -> np.ndarray:
    """Silero speech probability for every 512-sample (32 ms) frame of a 16 kHz clip. Used to find pauses (speech_check.py)."""
    global _vad
    n_frames = len(wav) // _FRAME
    with _vad_lock:
        if _vad is None:
            _vad = _Silero(config.ROOT / "assets" / "silero_vad.onnx")
        _vad.reset()
        return np.array([_vad(wav[i * _FRAME:(i + 1) * _FRAME]) for i in range(n_frames)])


def speech_span(wav: np.ndarray) -> float:
    """Seconds from the first to the last speech frame of a 16 kHz clip (0.0 if there is no speech). Pauses inside count."""
    voiced = np.flatnonzero(speech_probs(wav.astype(np.float32)) >= _SPEECH_THRESHOLD)
    return float((voiced[-1] + 1 - voiced[0]) * _FRAME / 16000) if len(voiced) else 0.0


def preemphasis(audio: np.ndarray, alpha: float = PREEMPHASIS_ALPHA) -> np.ndarray:
    out = np.empty_like(audio)
    out[0] = audio[0]
    out[1:] = audio[1:] - alpha * audio[:-1]
    return out


def pad_or_trim(audio: np.ndarray, target_len: int = PAD_INPUT_SAMPLES) -> np.ndarray:
    audio = audio.astype(np.float32)
    if len(audio) >= target_len:
        return audio[:target_len]
    return np.tile(audio, target_len // len(audio) + 1)[:target_len]


def prepare_wav(audio: np.ndarray) -> np.ndarray:
    """audio: 16 kHz mono float32."""
    wav = np.asarray(audio, dtype=np.float32).flatten()
    if len(wav) == 0:
        raise ValueError("Empty audio")
    return pad_or_trim(preemphasis(window_around_speech(wav)))
