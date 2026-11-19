"""Always-on Qwen3-TTS worker. Run with the qwen environment's Python (see start_demo.ps1).

  GET  /health -> {"ready": true, "device": "cuda:0", "batching": {...}}   (answers at any time, also while generating)
  POST /clone  {"ref", "ref_text", "text", "out"}  (absolute paths) -> {"ok": true, "seconds": ..., "sample_rate": ..., "batch_size": n}

Listens on 127.0.0.1 only and loads the model once. Requests are served by several threads, but the model is only ever
called from the batching thread (workers/batcher.py): requests that arrive within QWEN_BATCH_WINDOW_S of each other are
generated together as one batch of up to QWEN_MAX_BATCH, which takes about as long as a single clip.
"""
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import tailtrim  # noqa: E402
from workers.batcher import Batcher  # noqa: E402

os.environ.setdefault("HF_HOME", str(config.HF_HOME))
PORT = int(os.environ.get("QWEN_PORT", config.QWEN_URL.rsplit(":", 1)[1]))
MAX_BATCH = int(os.environ.get("QWEN_MAX_BATCH", "4"))
BATCH_WINDOW_S = float(os.environ.get("QWEN_BATCH_WINDOW_S", "2.0"))

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


TOKENS_PER_SECOND = 12.5      # the 12 Hz speech codec: the clip length at the token cap is max_new_tokens / 12.5


def generate(jobs: list[dict], budget: int):
    """One model call for these jobs. Returns (list of float32 numpy clips, sample rate)."""
    n = len(jobs)
    if n == 1:
        j = jobs[0]
        wavs, sr = MODEL.generate_voice_clone(text=j["text"], language="English", ref_audio=j["ref"], ref_text=j["ref_text"], max_new_tokens=budget)
    else:
        wavs, sr = MODEL.generate_voice_clone(text=[j["text"] for j in jobs], language=["English"] * n, ref_audio=[j["ref"] for j in jobs],
                                              ref_text=[j["ref_text"] for j in jobs], max_new_tokens=budget)
    return list(wavs), sr


def run_batch(jobs: list[dict]) -> list:
    """Generate all jobs with one model call. Returns one result dict (or Exception) per job, in order. Runs on the batching thread only.

    The model often does not stop at the end of the sentence and fills the rest of its token budget with loud noise, so every clip
    is cut just after the last speech (tailtrim.py). A clip still speaking at the cap is generated once more."""
    n = len(jobs)
    t0 = time.time()
    budget = max(token_budget(j["text"]) for j in jobs)          # a clip that ends sooner simply stops earlier
    cap_s = budget / TOKENS_PER_SECOND
    wavs, sr = generate(jobs, budget)
    trimmed = [tailtrim.trim_tail(w, sr, cap_s=cap_s) for w in wavs]
    retried = set()
    bad = [i for i, (_x, info) in enumerate(trimmed) if info["ran_on"]]
    if bad:
        print(f"{len(bad)} clip(s) still speaking at the cap: generating them again", flush=True)
        again, _ = generate([jobs[i] for i in bad], budget)
        for i, w in zip(bad, again):
            retried.add(i)
            second = tailtrim.trim_tail(w, sr, cap_s=cap_s)
            if not second[1]["ran_on"] or second[1]["speech_end"] < trimmed[i][1]["speech_end"]:
                trimmed[i] = second                                 # the new take ended properly (or at least earlier)
    seconds = round(time.time() - t0, 2)
    results = []
    for i, (j, (clip, info)) in enumerate(zip(jobs, trimmed)):
        try:
            os.makedirs(os.path.dirname(j["out"]), exist_ok=True)
            sf.write(j["out"], clip, sr)
            results.append({"ok": True, "seconds": seconds, "sample_rate": sr, "batch_size": n, "tail_trimmed_s": info["trimmed_s"],
                            "retried": i in retried, "ran_on": info["ran_on"]})
        except Exception as exc:  # noqa: BLE001
            results.append(exc)
    ends = ", ".join("%.1fs" % info["speech_end"] for _c, info in trimmed)
    cuts = ", ".join("%.1fs" % info["trimmed_s"] for _c, info in trimmed)
    print(f"batch of {n}: {seconds:.1f}s; speech ends at {ends}; tails cut: {cuts}", flush=True)
    return results


BATCHER = Batcher(run_batch, max_batch=MAX_BATCH, window_s=BATCH_WINDOW_S)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 64


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
        self._send(200, {"ready": True, "device": DEVICE, "dtype": str(DTYPE).removeprefix("torch."), "attn": ATTN, "batching": BATCHER.snapshot()})

    def do_POST(self):
        if self.path != "/clone":
            return self._send(404, {"error": "not found"})
        if MODEL is None:
            return self._send(503, {"ok": False, "error": LOAD_ERROR or "still loading"})
        try:
            job = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            result = BATCHER.submit({k: job[k] for k in ("ref", "ref_text", "text", "out")})
            self._send(200, result)
        except Exception as exc:  # noqa: BLE001
            print("clone failed:", type(exc).__name__, str(exc)[:200], flush=True)
            self._send(500, {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"})

    def log_message(self, *args):
        pass


Server((os.environ.get("QWEN_HOST", "127.0.0.1"), PORT), Handler).serve_forever()
