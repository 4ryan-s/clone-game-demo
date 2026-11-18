"""Always-on Qwen3-TTS worker. Run with the qwen environment's Python (see start_demo.ps1).

  GET  /health -> {"ready": true, "device": "cuda:0"}
  POST /clone  {"ref", "ref_text", "text", "out"}  (absolute paths) -> {"ok": true, "seconds": ..., "sample_rate": ...}
Listens on 127.0.0.1 only and handles one clone at a time. Loads the model once.
"""
import json
import os
import sys
import threading
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

ATTN = "sdpa"
if torch.cuda.is_available():
    major, _minor = torch.cuda.get_device_capability()
    if major >= 8:
        # bfloat16 and the fast attention kernels exist from Ampere (8.0) up.
        DEVICE, DTYPE, ATTN = "cuda:0", torch.bfloat16, "sdpa"
    else:
        # A T4 is Turing (7.5). Flash and memory-efficient attention abort there, and so can float16 sampling.
        torch.backends.cuda.enable_flash_sdp(False)
        torch.backends.cuda.enable_mem_efficient_sdp(False)
        torch.backends.cuda.enable_math_sdp(True)
        DEVICE, DTYPE, ATTN = "cuda:0", torch.float32, "eager"
elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
    DEVICE, DTYPE = "mps", torch.float32     # float32: half precision on Apple GPUs can give garbled audio
else:
    DEVICE, DTYPE = "cpu", torch.float32
MODEL = None
LOAD_ERROR = None


def load_model():
    """Load after the port is open. A health check during the load then gets a reply instead of connection refused."""
    global MODEL, ATTN, LOAD_ERROR
    print(f"loading {config.QWEN_MODEL} on {DEVICE} ({DTYPE}, {ATTN}) ...", flush=True)
    t0 = time.time()
    try:
        try:
            MODEL = Qwen3TTSModel.from_pretrained(config.QWEN_MODEL, device_map=DEVICE, dtype=DTYPE, attn_implementation=ATTN)
        except Exception as exc:  # noqa: BLE001
            print("attention load failed, retrying with the default attention:", str(exc)[:150], flush=True)
            ATTN = "default"
            MODEL = Qwen3TTSModel.from_pretrained(config.QWEN_MODEL, device_map=DEVICE, dtype=DTYPE)
        print(f"ready in {time.time() - t0:.0f}s", flush=True)
    except Exception as exc:  # noqa: BLE001
        LOAD_ERROR = f"{type(exc).__name__}: {exc}"
        print("model load failed:", LOAD_ERROR, flush=True)


threading.Thread(target=load_model, daemon=True).start()


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
        if self.path != "/health":
            return self._send(404, {"error": "not found"})
        if MODEL is None:
            return self._send(503, {"ready": False, "error": LOAD_ERROR or "loading"})
        self._send(200, {"ready": True, "device": DEVICE, "dtype": str(DTYPE).removeprefix("torch."), "attn": ATTN})

    def do_POST(self):
        if self.path != "/clone":
            return self._send(404, {"error": "not found"})
        if MODEL is None:
            return self._send(503, {"ok": False, "error": LOAD_ERROR or "still loading"})
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


HTTPServer((os.environ.get("QWEN_HOST", "127.0.0.1"), PORT), Handler).serve_forever()
