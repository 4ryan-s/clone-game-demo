"""Load test with REAL recordings already on the server (data/voice_samples/). ONE command, run on the server host:

    python3 tests/load_test.py --users 8            # add: --gap 4  --scenarios burst  --users 12 ...

For every simulated user it creates a session through the API, puts a saved recording (and its saved transcript) into the session,
calls /generate and polls /status until the clones are done - what a browser does after recording. It does NOT call speech to text
(no extra Sarvam cost) and does not touch the participants' stats. Test sessions are deleted afterwards; the voice bank is never modified.

Scenarios: "burst" (all users at the same moment) and "stagger" (one new user every --gap seconds).

Run on the host (where `docker` exists) it also, by itself: starts the test inside the api container, samples every container's RAM
and CPU and the GPU while it runs, and afterwards collects the Qwen worker / api log lines of the test. Everything is printed
and saved to load_test_report.txt: paste that file back. (Inside the container, without docker, it runs just the test.)
"""
import argparse
import csv
import json
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--users", type=int, default=8, help="simulated users per scenario")
ap.add_argument("--gap", type=float, default=5.0, help="seconds between new users in the stagger scenario")
ap.add_argument("--scenarios", default="burst,stagger", help="comma separated: burst, stagger")
ap.add_argument("--base", default="http://127.0.0.1:8000", help="the API as seen from where this runs")
ap.add_argument("--timeout", type=float, default=300, help="give up on one user after this many seconds")
ap.add_argument("--keep", action="store_true", help="do not delete the test sessions")
ap.add_argument("--inner", action="store_true", help=argparse.SUPPRESS)      # used by the host side to run the test inside the api container
args = ap.parse_args()


# ----------------------------------------------------------------------------------------------- host side (has docker)
def _mib(text):
    m = re.match(r"([\d.]+)\s*([KMG]i?B)", text.strip())
    if not m:
        return 0.0
    return float(m.group(1)) * {"KB": 1 / 1024, "KIB": 1 / 1024, "MB": 1, "MIB": 1, "GB": 1024, "GIB": 1024}[m.group(2).upper()]


def host_main():
    """Run the test inside the api container and watch everything around it. Needs only the python standard library."""
    report = []

    def out(line=""):
        print(line, flush=True)
        report.append(line)

    started = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())          # docker logs --since takes UTC when no zone is given
    stop = threading.Event()
    containers, gpu = {}, []

    def watch():
        while not stop.is_set():
            try:
                for ln in subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.Name}}|{{.MemUsage}}|{{.CPUPerc}}"],
                                         capture_output=True, text=True, timeout=30, cwd=ROOT).stdout.splitlines():
                    name, mem, cpu = (ln.split("|") + ["", ""])[:3]
                    c = containers.setdefault(name, {"mem": [], "cpu": []})
                    c["mem"].append(_mib(mem.split("/")[0]))
                    c["cpu"].append(float(cpu.strip("% ") or 0))
            except Exception:  # noqa: BLE001
                pass
            try:
                g = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=5).stdout.split(",")
                gpu.append((int(g[0]), int(g[1]), int(g[2])))
            except Exception:  # noqa: BLE001
                pass
            stop.wait(2)

    threading.Thread(target=watch, daemon=True).start()
    cmd = ["docker", "compose", "exec", "-T", "api", "python", "tests/load_test.py", "--inner"] + sys.argv[1:]
    out("$ " + " ".join(cmd))
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for ln in proc.stdout:
        out(ln.rstrip())
    code = proc.wait()
    stop.set()

    out("\n=== HOST RESOURCES DURING THE TEST (peak) ===")
    for name, c in sorted(containers.items()):
        if c["mem"]:
            out(f"  {name:28s} RAM peak {max(c['mem']):7.0f} MiB   CPU peak {max(c['cpu']):5.0f}%")
    if gpu:
        out(f"  GPU (nvidia-smi on host): memory peak {max(g[0] for g in gpu)}/{gpu[0][1]} MiB, utilisation avg "
            f"{statistics.mean(g[2] for g in gpu):.0f}% peak {max(g[2] for g in gpu)}%")
    else:
        out("  GPU: nvidia-smi not available on the host")

    keep = re.compile(r"batch|GPU memory|out of GPU|generated|qwen\.client|ERROR|WARNING|Traceback|OutOfMemory", re.I)
    for service, label in (("qwen", "QWEN WORKER 1"), ("qwen2", "QWEN WORKER 2"), ("api", "API (qwen.client / pipeline / errors only)")):
        r = subprocess.run(["docker", "compose", "logs", "--no-color", "--since", started, service], capture_output=True, text=True, cwd=ROOT)
        if r.returncode:
            continue                                                       # that service does not exist (for example qwen2 in the one-worker setup)
        pat = re.compile(r"qwen\.client|pipeline|ERROR|WARNING|OutOfMemory") if service == "api" else keep
        lines = [ln.split("|", 1)[-1].strip() for ln in r.stdout.splitlines() if pat.search(ln)]
        out(f"\n=== {label}: {len(lines)} relevant log lines" + (" (last 60 shown)" if len(lines) > 60 else "") + " ===")
        for ln in lines[-60:]:
            out("  " + ln[:230])
    (ROOT / "load_test_report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\nSaved to load_test_report.txt - paste that file back.")
    return code


if not args.inner and shutil.which("docker"):
    sys.exit(host_main())

# ------------------------------------------------------------------------------------- test side (inside the api container)
import requests  # noqa: E402

sys.path.insert(0, str(ROOT))
import config  # noqa: E402
import store  # noqa: E402


def pct(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(p * (len(values) - 1))))] if values else float("nan")


def load_recordings():
    """(wav path, transcript) for every saved voice-bank recording that has a transcript."""
    index = Path(config.VOICE_SAMPLES_DIR) / "index.csv"
    if not index.exists():
        sys.exit(f"No recordings found: {index} does not exist.")
    found = []
    with open(index, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            wav = Path(config.VOICE_SAMPLES_DIR) / f"{int(r['index']):06d}.wav"
            if r["status"] == "saved" and wav.is_file() and (r.get("transcript") or "").strip():
                found.append((wav, r["transcript"].strip()))
    if not found:
        sys.exit("No saved recording with a transcript was found in the voice bank.")
    return found


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

    def line(self):
        if not self.samples:
            return "GPU: nvidia-smi not available in this container"
        mem, util = [s[0] for s in self.samples], [s[2] for s in self.samples]
        return f"GPU memory peak {max(mem)}/{self.samples[0][1]} MiB (start {mem[0]}), utilisation avg {statistics.mean(util):.0f}% peak {max(util)}%"


def worker_health():
    out = {}
    for url in config.QWEN_URLS:
        try:
            out[url] = requests.get(url + "/health", timeout=5).json().get("batching", {})
        except Exception as exc:  # noqa: BLE001
            out[url] = {"error": type(exc).__name__}
    return out


def one_user(n, rec, results, sids):
    wav, transcript = rec
    t0 = time.time()
    res = {"user": n, "ok": False, "total": None, "engines": {}, "error": None}
    results[n] = res
    try:
        r = requests.post(args.base + "/api/sessions", json={"agree": True, "cloning": True, "retain": False, "version": config.CONSENT_VERSION}, timeout=30)
        r.raise_for_status()
        sid = r.json()["session_id"]
        sids.append(sid)
        d = store.path(sid)
        shutil.copyfile(wav, d / "original.wav")
        store.write(sid, "recording.json", {"ok": True, "issues": [], "transcript": transcript, "injected_by": "load_test"})
        t_gen = time.time()
        requests.post(f"{args.base}/api/sessions/{sid}/generate", timeout=30).raise_for_status()
        while True:
            st = requests.get(f"{args.base}/api/sessions/{sid}/status", timeout=30).json()
            if st["state"] in ("done", "error"):
                break
            if time.time() - t_gen > args.timeout:
                raise TimeoutError(f"no result after {args.timeout:.0f}s")
            time.sleep(1.0)
        res["total"] = time.time() - t_gen
        for name, v in store.read(sid, "meta.json", {}).get("engines", {}).items():
            res["engines"][name] = {"status": v["status"], "seconds": v.get("seconds"), "error": v.get("error")}
        res["ok"] = st["state"] == "done"
    except Exception as exc:  # noqa: BLE001
        res["error"] = f"{type(exc).__name__}: {str(exc)[:150]}"
        res["total"] = time.time() - t0


def run_scenario(name, recs):
    gap = args.gap if name == "stagger" else 0.0
    mon = GpuMonitor()
    mon.start()
    before = worker_health()
    results, sids, threads = {}, [], []
    t0 = time.time()
    for n in range(args.users):
        th = threading.Thread(target=one_user, args=(n, recs[n % len(recs)], results, sids))
        th.start()
        threads.append(th)
        if gap:
            time.sleep(gap)
    for th in threads:
        th.join()
    wall = time.time() - t0
    mon.stop.set()
    after = worker_health()
    rows = list(results.values())
    ok = [r for r in rows if r["ok"]]
    print(f"\n=== {name.upper()}: {args.users} users" + (f", one every {gap:g}s" if gap else " at the same moment") + f" | {len(recs)} distinct recordings ===")
    print(f"users fully OK: {len(ok)}/{len(rows)}   wall time {wall:.1f}s")
    totals = [r["total"] for r in ok]
    if totals:
        print(f"time until all clones ready, per user:  p50 {pct(totals, .5):.1f}s   p95 {pct(totals, .95):.1f}s   max {max(totals):.1f}s")
    per_engine = {}
    for r in rows:
        for eng, v in r["engines"].items():
            per_engine.setdefault(eng, []).append(v)
    for eng, vs in sorted(per_engine.items()):
        secs = [v["seconds"] for v in vs if v["status"] == "done" and v["seconds"] is not None]
        failed = [v for v in vs if v["status"] != "done"]
        line = f"  {eng:10s} done {len(secs)}/{len(vs)}"
        if secs:
            line += f"   p50 {pct(secs, .5):.1f}s  p95 {pct(secs, .95):.1f}s  max {max(secs):.1f}s"
        print(line)
        for v in failed[:2]:
            print(f"      failed: {str(v['error'])[:140]}")
    for r in rows:
        if r["error"]:
            print(f"  user {r['user']} error: {r['error']}")
    print("  " + mon.line())
    for url in before:
        b, a = before[url], after[url]
        if "error" in a:
            print(f"  worker {url}: unreachable ({a['error']})")
        else:
            print(f"  worker {url}: {a.get('batches', 0) - b.get('batches', 0)} batches, {a.get('jobs', 0) - b.get('jobs', 0)} clips, "
                  f"largest batch so far {a.get('largest_batch')}, max_batch setting {a.get('max_batch')}")
    if not args.keep:
        for sid in sids:
            store.delete(sid)
    return {"scenario": name, "users": args.users, "ok": len(ok), "wall_s": round(wall, 1),
            "total_p50": round(pct(totals, .5), 1) if totals else None, "total_p95": round(pct(totals, .95), 1) if totals else None}


recs = load_recordings()
print(f"Using {len(recs)} saved recording(s); workers: {config.QWEN_URLS}; Sarvam concurrency {config.SARVAM_CONCURRENCY}")
summary = [run_scenario(s.strip(), recs) for s in args.scenarios.split(",") if s.strip()]
print("\nSUMMARY_JSON " + json.dumps(summary))
