"""Always-on Qwen3-TTS worker. Run with the qwen environment's Python (see start_demo.ps1).

  GET  /health -> {"ready": true, "device": "cuda:0"}
  POST /clone  {"ref", "ref_text", "text", "out"}  (absolute paths) -> {"ok": true, "seconds": ..., "sample_rate": ...}
Listens on 127.0.0.1 only and handles one clone at a time. Loads the model once.
"""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

os.environ.setdefault("HF_HOME", str(config.HF_HOME))
PORT = int(os.environ.get("QWEN_PORT", config.QWEN_URL.rsplit(":", 1)[1]))

import soundfile as sf  # noqa: E402
import torch  # noqa: E402
from qwen_tts import Qwen3TTSModel  # noqa: E402

if torch.cuda.is_available():
    DEVICE, DTYPE = "cuda:0", torch.bfloat16
elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
    DEVICE, DTYPE = "mps", torch.float16
else:
    DEVICE, DTYPE = "cpu", torch.float32
print(f"loading {config.QWEN_MODEL} on {DEVICE} ...", flush=True)
t0 = time.time()
try:
    MODEL = Qwen3TTSModel.from_pretrained(config.QWEN_MODEL, device_map=DEVICE, dtype=DTYPE, attn_implementation="sdpa")
except Exception as exc:  # noqa: BLE001
    print("sdpa load failed, retrying with the default attention:", str(exc)[:150], flush=True)
    MODEL = Qwen3TTSModel.from_pretrained(config.QWEN_MODEL, device_map=DEVICE, dtype=DTYPE)
print(f"ready in {time.time() - t0:.0f}s", flush=True)


def token_budget(text: str) -> int:
    """The model speaks about 12 tokens per second. Cap the length so a runaway tail cannot run on."""
    seconds = min(14.0, 0.6 * len(text.split()) + 2.5)
    return int(12 * seconds)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send(200, {"ready": True, "device": DEVICE}) if self.path == "/health" else self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/clone":
            return self._send(404, {"error": "not found"})
        try:
            job = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            t = time.time()
            wavs, sr = MODEL.generate_voice_clone(text=job["text"], language="English", ref_audio=job["ref"],
                                                  ref_text=job["ref_text"], max_new_tokens=token_budget(job["text"]))
            os.makedirs(os.path.dirname(job["out"]), exist_ok=True)
            sf.write(job["out"], wavs[0], sr)
            self._send(200, {"ok": True, "seconds": round(time.time() - t, 2), "sample_rate": sr})
            print(f"clone done in {time.time() - t:.1f}s ({len(wavs[0]) / sr:.1f}s of audio)", flush=True)
        except Exception as exc:  # noqa: BLE001
            print("clone failed:", type(exc).__name__, str(exc)[:200], flush=True)
            self._send(500, {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"})

    def log_message(self, *args):
        pass


HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
