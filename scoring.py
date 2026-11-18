"""The clone check: Spectra-AASIST3, same preparation as the banking login (pre-emphasis on), RAW 16 kHz audio, no codec.
Margin = log-odds of "real" over "clone". Below config.CUTOFF the clip is called a clone.
The model file is config.SPECTRA_ONNX (models/spectra_aasist3.onnx, put there by setup.py).

SPECTRA_DEVICE=cuda loads this model on the GPU and refuses to fall back to CPU.
The voice-activity step in spectra_prep stays on CPU.
"""
import logging
import os
import threading

import numpy as np
import onnxruntime as ort

import config
import spectra_prep

log = logging.getLogger("spectra")
_lock = threading.Lock()
_sess = None
_provider = ""
_ready = threading.Event()
_error = None


def _providers() -> list[str]:
    if os.environ.get("SPECTRA_DEVICE", "cpu") == "cuda":
        return ["CUDAExecutionProvider"]
    return ["CPUExecutionProvider"]


def _load():
    global _sess, _provider, _error
    try:
        if not config.SPECTRA_ONNX.is_file():
            raise FileNotFoundError(f"{config.SPECTRA_ONNX} is missing. Run `python setup.py` or set SPECTRA_ONNX.")
        sess = ort.InferenceSession(str(config.SPECTRA_ONNX), providers=_providers())
        active = sess.get_providers()[0]
        if os.environ.get("SPECTRA_DEVICE") == "cuda" and active != "CUDAExecutionProvider":
            raise RuntimeError(f"Spectra did not load on the GPU (got {active})")
        _sess = sess
        _provider = active
        log.info("clone check ready on %s", active)
    except Exception as exc:  # noqa: BLE001
        _error = str(exc)
        log.warning("clone check failed to load: %s", _error)
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


def device() -> str:
    return _provider


def ready() -> tuple[bool, str]:
    return (_ready.is_set() and _sess is not None, _error or ("" if _ready.is_set() else "loading"))
