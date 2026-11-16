"""The clone check: Spectra-AASIST3, same preparation as the banking login (pre-emphasis on), RAW 16 kHz audio, no codec.
Margin = log-odds of "real" over "clone". Below config.CUTOFF the clip is called a clone.
Reuses the banking backend's prepare_wav and ONNX model by path (config.SPECTRA_BACKEND), read-only; nothing is copied or changed there."""
import sys
import threading

import numpy as np

import config

_lock = threading.Lock()
_sess = None
_prepare = None
_ready = threading.Event()
_error = None


def _load():
    global _sess, _prepare, _error
    try:
        sys.path.insert(0, str(config.SPECTRA_BACKEND))
        from voiceprint.utils.pad_scorer import prepare_wav
        import onnxruntime as ort
        _prepare = prepare_wav
        _sess = ort.InferenceSession(str(config.SPECTRA_BACKEND / "model" / "spectra_aasist3.onnx"), providers=["CPUExecutionProvider"])
    except Exception as exc:  # noqa: BLE001
        _error = str(exc)
    finally:
        _ready.set()


def warm_up() -> None:
    """Load the model in the background at server start (it is 1.2 GB; the first load takes a while)."""
    threading.Thread(target=_load, daemon=True).start()


def margin(x: np.ndarray) -> float:
    if not _ready.is_set():
        warm_up()
    _ready.wait()
    if _sess is None:
        raise RuntimeError(f"The clone check could not be loaded: {_error}")
    w = _prepare(x, 16000, use_preemphasis=True)
    with _lock:
        logits = _sess.run(["logits"], {"wav": w[None, :].astype(np.float32)})[0][0]
    return float(logits[1] - logits[0])


def ready() -> tuple[bool, str]:
    return (_ready.is_set() and _sess is not None, _error or ("" if _ready.is_set() else "loading"))
