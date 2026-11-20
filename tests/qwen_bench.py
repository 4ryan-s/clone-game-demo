"""Concurrency benchmark for the Qwen3-TTS workers, with GPU monitoring. Compare setups (1 worker vs 2) by running it for each.

    docker compose exec api python tests/qwen_bench.py --ref /app/data/ref.wav --ref-text "what the ref says" \
        --urls http://qwen:8766,http://qwen2:8766 [--clients 8] [--gap 4]
    (--ref and --out-dir are paths as the WORKER sees them, i.e. inside the container: put the ref under ./data)

Requests are routed like engines/qwen3tts.py does: to the URL with the fewest requests in flight.
Scenarios: "burst" (all clients at once) and "stagger" (one client every --gap seconds).
Reports per-request total latency (p50 / p95 / max), wall time, and GPU memory / utilisation sampled once a second.
"""
import argparse
import statistics
import subprocess
import threading
import time
from pathlib import Path

import requests

ap = argparse.ArgumentParser()
ap.add_argument("--urls", default="http://127.0.0.1:8766", help="comma separated worker URLs")
ap.add_argument("--ref", required=True)
ap.add_argument("--ref-text", required=True)
ap.add_argument("--text", default="Hello everyone! I'm here in Hyderabad, India, attending the Ruby Conference today. Looking forward to an amazing experience!")
ap.add_argument("--out-dir", default="/app/data/bench")
ap.add_argument("--clients", type=int, default=8)
ap.add_argument("--gap", type=float, default=4.0, help="seconds between arrivals in the stagger scenario")
ap.add_argument("--rounds", type=int, default=1)
args = ap.parse_args()
URLS = [u.strip().rstrip("/") for u in args.urls.split(",") if u.strip()]
IN_FLIGHT = {u: 0 for u in URLS}
LOCK = threading.Lock()
Path(args.out_dir).mkdir(parents=True, exist_ok=True)


def gpu_sample():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5).stdout.split(",")
        return int(out[0]), int(out[1]), int(out[2])
    except Exception:  # noqa: BLE001
        return None


class GpuMonitor(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.samples, self.stop = [], threading.Event()

    def run(self):
        while not self.stop.is_set():
            s = gpu_sample()
            if s:
                self.samples.append(s)
            self.stop.wait(1.0)

    def report(self):
        if not self.samples:
            return "GPU: nvidia-smi not available here (run it on the host: watch -n1 nvidia-smi)"
        mem, tot, util = [s[0] for s in self.samples], self.samples[0][1], [s[2] for s in self.samples]
        return f"GPU: peak memory {max(mem)}/{tot} MiB, GPU utilisation avg {statistics.mean(util):.0f}% peak {max(util)}%"


def one_request(idx, tag, results):
    t0 = time.time()
    payload = {"ref": args.ref, "ref_text": args.ref_text, "text": args.text, "out": f"{args.out_dir}/{tag}_{idx}.wav"}
    err = None
    with LOCK:
        order = sorted(URLS, key=lambda u: IN_FLIGHT[u])
    for url in order:
        with LOCK:
            IN_FLIGHT[url] += 1
        try:
            r = requests.post(url + "/clone", json=payload, timeout=600)
            if r.status_code == 503:
                err = "503"
                continue
            body = r.json()
            results[idx] = (time.time() - t0, body.get("batch_size"), url, None if body.get("ok") else str(body)[:100])
            return
        except Exception as exc:  # noqa: BLE001
            err = type(exc).__name__
        finally:
            with LOCK:
                IN_FLIGHT[url] -= 1
    results[idx] = (time.time() - t0, None, None, err)


def scenario(name, gap):
    mon = GpuMonitor()
    mon.start()
    results, threads = {}, []
    t0 = time.time()
    for i in range(args.clients):
        th = threading.Thread(target=one_request, args=(i, name, results))
        th.start()
        threads.append(th)
        if gap:
            time.sleep(gap)
    for th in threads:
        th.join()
    wall = time.time() - t0
    mon.stop.set()
    lat = sorted(r[0] for r in results.values() if not r[3])
    fails = [r[3] for r in results.values() if r[3]]
    print(f"\n== {name}: {args.clients} clients, workers={len(URLS)}" + (f", one every {gap}s" if gap else ", all at once"))
    if lat:
        p95 = lat[min(len(lat) - 1, int(round(0.95 * (len(lat) - 1))))]
        print(f"   latency  p50 {statistics.median(lat):.1f}s   p95 {p95:.1f}s   max {lat[-1]:.1f}s   wall {wall:.1f}s")
    sizes = [r[1] for r in results.values() if r[1]]
    if sizes:
        print(f"   batch sizes seen: {sorted(set(sizes))}   per worker: " + ", ".join(f"{u}={sum(1 for r in results.values() if r[2] == u)}" for u in URLS))
    if fails:
        print(f"   FAILED {len(fails)}: {fails[:3]}")
    print("   " + mon.report())


for u in URLS:
    h = requests.get(u + "/health", timeout=5)
    print(u, "health:", h.status_code, h.json())
for rnd in range(args.rounds):
    scenario("burst", 0)
    scenario("stagger", args.gap)
