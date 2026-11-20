"""Routing between several Qwen workers (engines/qwen3tts.py), with the network mocked. Runs without a GPU."""
import sys
import threading
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# Heavy audio libraries are not needed to test routing: stub whichever are not installed.
for _name in ("soundfile", "numpy", "scipy", "scipy.signal", "librosa", "onnxruntime", "torch", "torchaudio"):
    try:
        __import__(_name)
    except ImportError:
        sys.modules[_name] = mock.MagicMock()
import config  # noqa: E402

config.QWEN_URLS = ["http://a:1", "http://b:1"]
from engines import qwen3tts  # noqa: E402
from engines.base import EngineError  # noqa: E402

qwen3tts._IN_FLIGHT.clear()
qwen3tts._IN_FLIGHT.update({u: 0 for u in config.QWEN_URLS})


import base64  # noqa: E402
import tempfile  # noqa: E402

_REF = Path(tempfile.mkdtemp()) / "ref.wav"
_REF.write_bytes(b"RIFFfake")
_OK = {"ok": True, "sample_rate": 24000, "audio_b64": base64.b64encode(b"RIFFout").decode()}


class Resp:
    def __init__(self, code=200, body=None):
        self.status_code, self._b, self.text = code, body or dict(_OK), "x"
        self.ok = code == 200

    def json(self):
        return self._b


def clone():
    return qwen3tts.Qwen3TTS().clone(_REF, "t", "hello", _REF.parent / "out" / "o.wav")


def test_spreads_concurrent_requests():
    seen, lock = [], threading.Lock()

    def post(url, **kw):
        with lock:
            seen.append(url)
        time.sleep(0.2)
        return Resp()

    with mock.patch("requests.post", post):
        ts = [threading.Thread(target=clone) for _ in range(4)]
        [t.start() for t in ts]
        [t.join() for t in ts]
    assert sorted(seen) == ["http://a:1/clone"] * 2 + ["http://b:1/clone"] * 2, seen
    assert all(v == 0 for v in qwen3tts._IN_FLIGHT.values())


def test_falls_over_when_a_worker_is_down_or_loading():
    import requests

    def post(url, **kw):
        if url.startswith("http://a"):
            raise requests.ConnectionError()
        return Resp()

    with mock.patch("requests.post", post):
        assert clone()["sample_rate"] == 24000
    with mock.patch("requests.post", lambda url, **kw: Resp(503) if url.startswith("http://a") else Resp()):
        assert clone()
    assert all(v == 0 for v in qwen3tts._IN_FLIGHT.values())


def test_all_down_raises_engine_error():
    import requests
    with mock.patch("requests.post", side_effect=requests.ConnectionError()):
        try:
            clone()
        except EngineError:
            return
    raise AssertionError("expected EngineError")


def test_model_failure_is_not_retried():
    calls = []

    def post(url, **kw):
        calls.append(url)
        return Resp(500, {"ok": False})

    with mock.patch("requests.post", post):
        try:
            clone()
        except EngineError:
            pass
    assert len(calls) == 1


def test_available_if_any_ready():
    def get(url, **kw):
        return Resp(200, {"ready": url.startswith("http://b")})

    with mock.patch("requests.get", get):
        assert qwen3tts.Qwen3TTS().available()[0] is True
    with mock.patch("requests.get", lambda url, **kw: Resp(503, {"ready": False})):
        assert qwen3tts.Qwen3TTS().available()[0] is False


def test_audio_comes_back_over_http_and_the_ref_is_sent():
    sent = {}

    def post(url, **kw):
        sent.update(kw["json"])
        return Resp()

    with mock.patch("requests.post", post):
        clone()
    assert base64.b64decode(sent["ref_b64"]) == b"RIFFfake" and "ref" not in sent
    assert (_REF.parent / "out" / "o.wav").read_bytes() == b"RIFFout"


def test_a_worker_that_just_failed_is_skipped_for_a_while():
    import requests
    calls = []

    def post(url, **kw):
        calls.append(url)
        if url.startswith("http://a"):
            raise requests.ConnectionError()
        return Resp()

    qwen3tts._DOWN_UNTIL.update({u: 0.0 for u in config.QWEN_URLS})
    with mock.patch("requests.post", post):
        clone()                                  # a is tried first, fails, b answers
        calls.clear()
        clone()                                  # a is marked down: b goes first
    assert calls == ["http://b:1/clone"], calls
    qwen3tts._DOWN_UNTIL.update({u: 0.0 for u in config.QWEN_URLS})


def test_a_slow_worker_is_not_treated_as_down_and_the_clip_is_not_sent_twice():
    import requests
    calls = []

    def post(url, **kw):
        calls.append(url)
        raise requests.ReadTimeout()

    qwen3tts._DOWN_UNTIL.update({u: 0.0 for u in config.QWEN_URLS})
    with mock.patch("requests.post", post):
        try:
            clone()
        except EngineError:
            pass
        else:
            raise AssertionError("expected EngineError")
    assert len(calls) == 1, calls
    assert all(v == 0.0 for v in qwen3tts._DOWN_UNTIL.values())
