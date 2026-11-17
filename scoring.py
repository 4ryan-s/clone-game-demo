"""The clone check: Spectra-AASIST3, same preparation as the banking login (pre-emphasis on), RAW 16 kHz audio, no codec.
Margin = log-odds of "real" over "clone". Below config.CUTOFF the clip is called a clone.
The model file is config.SPECTRA_ONNX (models/spectra_aasist3.onnx, put there by setup.py)."""
import threading

import numpy as np
import onnxruntime as ort

import config
import spectra_prep

_lock = threading.Lock()
_sess = None
_ready = threading.Event()
_error = None


def _load():
    global _sess, _error
    try:
        if not config.SPECTRA_ONNX.is_file():
            raise FileNotFoundError(f"{config.SPECTRA_ONNX} is missing. Run `python setup.py` or set SPECTRA_ONNX.")
        _sess = ort.InferenceSession(str(config.SPECTRA_ONNX), providers=["CPUExecutionProvider"])
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
    w = spectra_prep.prepare_wav(x)
    with _lock:
        logits = _sess.run(["logits"], {"wav": w[None, :].astype(np.float32)})[0][0]
    return float(logits[1] - logits[0])


def ready() -> tuple[bool, str]:
    return (_ready.is_set() and _sess is not None, _error or ("" if _ready.is_set() else "loading"))
