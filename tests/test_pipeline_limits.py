"""pipeline._lock_for: Qwen is not locked, Sarvam allows SARVAM_CONCURRENCY at once. No GPU or network needed."""
import sys
import threading
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
for _name in ("soundfile", "numpy", "scipy", "scipy.signal", "librosa", "onnxruntime", "torch", "torchaudio"):
    try:
        __import__(_name)
    except ImportError:
        sys.modules[_name] = mock.MagicMock()
import pipeline  # noqa: E402
from engines.base import Engine  # noqa: E402
from engines.qwen3tts import Qwen3TTS  # noqa: E402


def test_qwen_is_not_serialized():
    assert Qwen3TTS.serialize is False


def test_semaphore_limits_concurrency():
    class Fake(Engine):
        name = "fake"
        lock_group = "fake-group"
        max_concurrent = 2

    running, peak, guard = 0, 0, threading.Lock()

    def work():
        nonlocal running, peak
        with pipeline._lock_for(Fake()):
            with guard:
                running += 1
                peak = max(peak, running)
            time.sleep(0.1)
            with guard:
                running -= 1

    ts = [threading.Thread(target=work) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert peak == 2, peak
