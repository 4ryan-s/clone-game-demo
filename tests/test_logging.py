"""The access-log filter, and the per-session summary line of the pipeline. No GPU, network or audio libraries needed."""
import logging
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
for _name in ("soundfile", "scipy", "scipy.signal", "librosa", "onnxruntime", "torch", "torchaudio"):
    try:
        __import__(_name)
    except ImportError:
        sys.modules[_name] = mock.MagicMock()
import config  # noqa: E402
import logsetup  # noqa: E402


def _access(path, status):
    return logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d', ("1.2.3.4:5", "GET", path, "1.1", status), None)


def test_access_log_drops_noise_but_keeps_real_requests_and_errors():
    f = logsetup.QuietAccessLog()
    assert not f.filter(_access("/api/sessions/abc/status", 200))
    assert not f.filter(_access("/api/health", 200))
    assert not f.filter(_access("/assets/index-1.js", 200))
    assert f.filter(_access("/api/sessions/abc/recording", 200))
    assert f.filter(_access("/api/sessions/abc/status", 500))        # a failing poll is still shown
    assert f.filter(_access("/api/sessions/abc/cards", 409))


def test_pipeline_logs_one_summary_line_per_session(caplog):
    import numpy as np
    import pipeline
    import store

    config.SESSIONS_DIR = Path(tempfile.mkdtemp())
    sid = store.new_id()
    (config.SESSIONS_DIR / sid).mkdir()
    (config.SESSIONS_DIR / sid / "original.wav").write_bytes(b"x")
    store.write(sid, "recording.json", {"transcript": "hello there"})

    class Fake:
        serialize, lock_key, max_concurrent = False, "fake", 1

        def __init__(self, name, info):
            self.name, self._info = name, info

        def available(self):
            return True, ""

        def clone(self, ref, ref_text, text, out):
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"x")
            if self.name == "bad":
                raise RuntimeError("boom")
            return self._info

    fakes = [Fake("sarvam", {}), Fake("qwen3tts", {"worker": "qwen", "batch_size": 4, "queue_wait_s": 1.5, "generation_s": 30.0}), Fake("bad", {})]
    with mock.patch.object(pipeline, "audio", SimpleNamespace(read_wav_bytes=lambda b: (np.zeros(10, dtype="float32"), 16000),
                                                              to_16k=lambda x, sr: x, write_wav=lambda p, x: None)), caplog.at_level(logging.INFO):
        store.update_meta(sid, lambda m: m.update(state="running", started_at=0.0, engines={f.name: {"slot": f"c{i}", "status": "running", "seconds": None, "error": None}
                                                                                            for i, f in enumerate(fakes, 1)}))
        pipeline._run(sid, fakes, {f.name: f"c{i}" for i, f in enumerate(fakes, 1)})
    lines = [r.getMessage() for r in caplog.records if "clones" in r.getMessage()]
    assert len(lines) == 1, lines
    line = lines[0]
    assert "ERROR" in line and "qwen3tts=done" in line and "worker qwen, batch of 4, waited 1.5s" in line and "bad=error" in line and "boom" in line, line
    assert "hello there" not in caplog.text                       # the transcript never goes to the log
