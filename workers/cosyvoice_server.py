"""Always-on CosyVoice 2 worker. Run with the cosyvoice venv's Python (see start_demo.ps1).

Loads the model once, then answers:
  GET  /health -> {"ready": true, "sample_rate": 24000}
  POST /clone  {"ref", "ref_text", "text", "out"}  (absolute paths) -> {"ok": true, "seconds": ..., "sample_rate": ...}
Listens on 127.0.0.1 only and handles one clone at a time (the model is not thread-safe).
"""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

REPO = config.COSYVOICE_REPO.as_posix()
PORT = int(os.environ.get("COSYVOICE_PORT", config.COSYVOICE_URL.rsplit(":", 1)[1]))
os.chdir(REPO)
sys.path.append(REPO)
sys.path.append(REPO + "/third_party/Matcha-TTS")

import torch  # noqa: E402
import torchaudio  # noqa: E402
from cosyvoice.cli.cosyvoice import AutoModel  # noqa: E402

print("loading CosyVoice2-0.5B ...", flush=True)
t0 = time.time()
MODEL = AutoModel(model_dir=config.COSYVOICE_MODEL_DIR.as_posix())
print(f"ready in {time.time() - t0:.0f}s, cuda={torch.cuda.is_available()}, sample_rate={MODEL.sample_rate}", flush=True)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"ready": True, "sample_rate": MODEL.sample_rate})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/clone":
            return self._send(404, {"error": "not found"})
        try:
            job = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            t = time.time()
            chunks = [c["tts_speech"] for c in MODEL.inference_zero_shot(job["text"], job["ref_text"], job["ref"], stream=False)]
            wav = torch.cat(chunks, dim=1)
            os.makedirs(os.path.dirname(job["out"]), exist_ok=True)
            torchaudio.save(job["out"], wav, MODEL.sample_rate)
            self._send(200, {"ok": True, "seconds": round(time.time() - t, 2), "sample_rate": MODEL.sample_rate})
            print(f"clone done in {time.time() - t:.1f}s", flush=True)
        except Exception as exc:  # noqa: BLE001
            print("clone failed:", type(exc).__name__, str(exc)[:200], flush=True)
            self._send(500, {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"})

    def log_message(self, *args):  # keep the console quiet
        pass


HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
