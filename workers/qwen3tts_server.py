"""Always-on Qwen3-TTS worker. Run with the qwen environment's Python (see start_demo.ps1).

  GET  /health -> {"ready": true, "device": "cuda:0", "batching": {...}}   (answers at any time, also while generating)
  POST /clone  {"ref_b64" (base64 WAV), "ref_text", "text"} -> {"ok": true, "audio_b64": ..., "seconds": ..., "sample_rate": ..., "batch_size": n, ...}
               Audio travels in the request and the reply, so the worker can run on another machine.
               (Old same-disk mode with "ref"/"out" paths: only when QWEN_ALLOW_PATHS=1, for tests/qwen_worker_live.py.)

Binds to QWEN_HOST (default 127.0.0.1; the compose files use 0.0.0.0). Anything reachable from a network MUST set QWEN_TOKEN (sent as the
X-Qwen-Token header); traffic is plain HTTP, so use a private network or VPN between machines. It loads the model once. Requests are served
by several threads, but the model is only ever called from the batching thread (workers/batcher.py): requests that arrive within
QWEN_BATCH_WINDOW_S of each other are generated together as one batch of up to QWEN_MAX_BATCH, which takes about as long as a single clip.
"""
import base64
import hmac
import json
import logging
import os
import re
import shutil
import socket
import tempfile
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import tailtrim  # noqa: E402
from workers.batcher import Batcher  # noqa: E402

WORKER = os.environ.get("QWEN_WORKER_NAME") or socket.gethostname()
logging.basicConfig(level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
                    format=f"%(asctime)s %(levelname)-7s [{WORKER}] %(name)s: %(message)s")
log = logging.getLogger("qwen")

os.environ.setdefault("HF_HOME", str(config.HF_HOME))
PORT = int(os.environ.get("QWEN_PORT", config.QWEN_URL.rsplit(":", 1)[1]))
TOKEN = os.environ.get("QWEN_TOKEN", "")
ALLOW_PATHS = os.environ.get("QWEN_ALLOW_PATHS", "") == "1"          # legacy: caller names file paths on this machine (never enable on a network-exposed worker)
MAX_BODY_BYTES = 24 * 1024 * 1024                                  # a recording is at most 8 MB, which is about 11 MB as base64
MAX_BATCH = int(os.environ.get("QWEN_MAX_BATCH", "4"))
BATCH_WINDOW_S = float(os.environ.get("QWEN_BATCH_WINDOW_S", "2.0"))

import soundfile as sf  # noqa: E402
import torch  # noqa: E402
from qwen_tts import Qwen3TTSModel  # noqa: E402

ATTN = "sdpa"
if torch.cuda.is_available():
    # With several workers on one GPU, cap this process so they cannot starve each other (e.g. 0.4 = 40% of the card).
    _frac = float(os.environ.get("QWEN_GPU_MEM_FRACTION", "0") or 0)
    if 0 < _frac < 1:
        torch.cuda.set_per_process_memory_fraction(_frac)
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
# One generate at a time. A second visitor waits; their health check must still get an answer.
_CLONE_LOCK = threading.Lock()


def gpu_mem() -> str:
    if DEVICE != "cuda:0":
        return "no GPU"
    mib = 1024 * 1024
    return "GPU memory: %d MiB in use by tensors, %d MiB reserved, peak %d MiB" % (
        torch.cuda.memory_allocated() // mib, torch.cuda.memory_reserved() // mib, torch.cuda.max_memory_allocated() // mib)


def load_model():
    """Load after the port is open. A health check during the load then gets a reply instead of connection refused."""
    global MODEL, ATTN, LOAD_ERROR
    log.info("loading %s on %s (%s, %s), max batch %d, window %.1fs", config.QWEN_MODEL, DEVICE, DTYPE, ATTN, MAX_BATCH, BATCH_WINDOW_S)
    if DEVICE == "cuda:0":
        free, total = (v // (1024 * 1024) for v in torch.cuda.mem_get_info())
        log.info("GPU before loading: %d of %d MiB free%s", free, total, "  <- LOW: another process is holding the GPU" if free < 7000 else "")
    t0 = time.time()
    try:
        try:
            MODEL = Qwen3TTSModel.from_pretrained(config.QWEN_MODEL, device_map=DEVICE, dtype=DTYPE, attn_implementation=ATTN)
        except Exception as exc:  # noqa: BLE001
            log.warning("attention load failed, retrying with the default attention: %s", str(exc)[:150])
            ATTN = "default"
            MODEL = Qwen3TTSModel.from_pretrained(config.QWEN_MODEL, device_map=DEVICE, dtype=DTYPE)
        log.info("ready in %.0fs; %s", time.time() - t0, gpu_mem())
    except Exception as exc:  # noqa: BLE001
        LOAD_ERROR = f"{type(exc).__name__}: {exc}"
        log.error("model load failed: %s", LOAD_ERROR)


threading.Thread(target=load_model, daemon=True).start()


BUDGET_REF_FACTOR = float(os.environ.get("QWEN_BUDGET_REF_FACTOR", "0") or 0)      # 0 = off. e.g. 1.3: cap each clip at 1.3 x the reference recording's length + 1 s


def job_budget(job: dict) -> int:
    """Token cap for one request. The clone says the same words as the reference recording, so it should last about as long.
    With QWEN_BUDGET_REF_FACTOR set, the cap is tightened to that: a clip that runs on (see tailtrim) then costs the whole batch less time."""
    base = token_budget(job["text"])
    if BUDGET_REF_FACTOR > 0:
        try:
            ref_s = sf.info(job["ref"]).duration
            return min(base, max(60, int(TOKENS_PER_SECOND * (ref_s * BUDGET_REF_FACTOR + 1.0))))
        except Exception:  # noqa: BLE001
            pass
    return base


def token_budget(text: str) -> int:
    """The model speaks about 12 tokens per second. Cap the length so a runaway tail cannot run on."""
    seconds = min(14.0, 0.6 * len(text.split()) + 2.5)
    return int(12 * seconds)


TOKENS_PER_SECOND = 12.5      # the 12 Hz speech codec: the clip length at the token cap is max_new_tokens / 12.5


def _generate(jobs: list[dict], budget: int):
    n = len(jobs)
    if n == 1:
        j = jobs[0]
        wavs, sr = MODEL.generate_voice_clone(text=j["text"], language="English", ref_audio=j["ref"], ref_text=j["ref_text"], max_new_tokens=budget)
    else:
        wavs, sr = MODEL.generate_voice_clone(text=[j["text"] for j in jobs], language=["English"] * n, ref_audio=[j["ref"] for j in jobs],
                                              ref_text=[j["ref_text"] for j in jobs], max_new_tokens=budget)
    return list(wavs), sr


def generate(jobs: list[dict], budget: int):
    """One model call for these jobs. Returns (list of float32 numpy clips, sample rate).
    If the GPU runs out of memory the cache is freed and the batch is split in two (down to single clips), so users still get a clip."""
    try:
        return _generate(jobs, budget)
    except torch.cuda.OutOfMemoryError:
        torch.cuda.empty_cache()
        if len(jobs) == 1:
            raise
        log.warning("out of GPU memory with a batch of %d: splitting it in two (%s)", len(jobs), gpu_mem())
        half = len(jobs) // 2
        a, sr = generate(jobs[:half], budget)
        b, _ = generate(jobs[half:], budget)
        return a + b, sr


def run_batch(jobs: list[dict]) -> list:
    """Generate all jobs with one model call. Returns one result dict (or Exception) per job, in order. Runs on the batching thread only.

    The model often does not stop at the end of the sentence and fills the rest of its token budget with loud noise, so every clip
    is cut just after the last speech (tailtrim.py). A clip still speaking at the cap is generated once more."""
    n = len(jobs)
    t0 = time.time()
    budget = max(job_budget(j) for j in jobs)          # a clip that ends sooner simply stops earlier
    cap_s = budget / TOKENS_PER_SECOND
    wavs, sr = generate(jobs, budget)
    trimmed = [tailtrim.trim_tail(w, sr, cap_s=cap_s) for w in wavs]
    retried = set()
    bad = [i for i, (_x, info) in enumerate(trimmed) if info["ran_on"]]
    if bad:
        log.warning("%d clip(s) still speaking at the cap: generating them again", len(bad))
        again, _ = generate([jobs[i] for i in bad], budget)
        for i, w in zip(bad, again):
            retried.add(i)
            second = tailtrim.trim_tail(w, sr, cap_s=cap_s)
            if not second[1]["ran_on"] or second[1]["speech_end"] < trimmed[i][1]["speech_end"]:
                trimmed[i] = second                                 # the new take ended properly (or at least earlier)
    seconds = round(time.time() - t0, 2)
    if DEVICE == "cuda:0":
        torch.cuda.empty_cache()          # give cached blocks back so the other GPU user (the clone check in the api) is not starved
    results = []
    for i, (j, (clip, info)) in enumerate(zip(jobs, trimmed)):
        try:
            os.makedirs(os.path.dirname(j["out"]), exist_ok=True)
            sf.write(j["out"], clip, sr)
            results.append({"ok": True, "seconds": seconds, "sample_rate": sr, "batch_size": n, "tail_trimmed_s": info["trimmed_s"],
                            "retried": i in retried, "ran_on": info["ran_on"], "worker": WORKER})
        except Exception as exc:  # noqa: BLE001
            results.append(exc)
    ends = ", ".join("%.1fs" % info["speech_end"] for _c, info in trimmed)
    cuts = ", ".join("%.1fs" % info["trimmed_s"] for _c, info in trimmed)
    log.info("generated %d clip(s) in %.1fs (budget %d tokens, %d retried); speech ends at %s; tails cut: %s; %s",
             n, seconds, budget, len(retried), ends, cuts, gpu_mem())
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
        if TOKEN and not hmac.compare_digest(self.headers.get("X-Qwen-Token", "").encode(), TOKEN.encode()):
            log.warning("refused a request from %s: bad or missing X-Qwen-Token", self.client_address[0])
            return self._send(401, {"ok": False, "error": "bad or missing X-Qwen-Token"})
        if MODEL is None:
            return self._send(503, {"ok": False, "error": LOAD_ERROR or "still loading"})
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return self._send(400, {"ok": False, "error": "bad Content-Length"})
        if length > MAX_BODY_BYTES:
            log.warning("refused a request from %s: %d bytes is over the %d byte limit", self.client_address[0], length, MAX_BODY_BYTES)
            return self._send(413, {"ok": False, "error": "request too large"})
        tmp = None
        payload = {}
        try:
            try:
                job = json.loads(self.rfile.read(length))
                ref_b64 = job.get("ref_b64")
                tag = re.sub(r"[^A-Za-z0-9_-]", "", str(job.get("tag", "")))[:16]
                if ref_b64:
                    ref_bytes = base64.b64decode(ref_b64, validate=True)
                    payload = {"ref_text": job["ref_text"], "text": job["text"], "tag": tag}
                elif ALLOW_PATHS:
                    payload = {k: job[k] for k in ("ref", "ref_text", "text", "out")}
                else:
                    raise ValueError("send the reference audio as ref_b64")
            except (ValueError, KeyError, TypeError, AttributeError) as exc:          # includes bad JSON and bad base64: the caller's mistake, not ours
                log.warning("bad request from %s: %s: %s", self.client_address[0], type(exc).__name__, str(exc)[:120])
                return self._send(400, {"ok": False, "error": f"bad request: {type(exc).__name__}: {str(exc)[:120]}"})
            if ref_b64:
                # Audio travels in the request and comes back in the reply, so the worker needs no shared disk (it can run on another machine).
                tmp = tempfile.mkdtemp(prefix="qwen_")
                payload["ref"], payload["out"] = os.path.join(tmp, "ref.wav"), os.path.join(tmp, "out.wav")
                with open(payload["ref"], "wb") as fh:
                    fh.write(ref_bytes)
            result = BATCHER.submit(payload)
            if tmp:
                with open(payload["out"], "rb") as fh:
                    result = {**result, "audio_b64": base64.b64encode(fh.read()).decode()}
            self._send(200, result)
        except Exception as exc:  # noqa: BLE001
            log.error("clone request [%s] failed: %s: %s", payload.get("tag", "-"), type(exc).__name__, str(exc)[:200])
            return self._send(500, {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
        finally:
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)

    def log_message(self, *args):
        pass


HOST = os.environ.get("QWEN_HOST", "127.0.0.1")
if HOST not in ("127.0.0.1", "localhost", "::1") and not TOKEN:
    log.warning("listening on %s without QWEN_TOKEN: anyone who can reach port %d can use this worker. Fine only on a private docker network; "
                "set QWEN_TOKEN when the port is reachable from other machines", HOST, PORT)
Server((HOST, PORT), Handler).serve_forever()
