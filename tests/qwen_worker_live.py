"""Live check of the Qwen worker's batching against a running worker (needs a GPU and the model).
    python tests/qwen_worker_live.py [worker_url] [ref_dir]
Sends 1, 2, 4 and 6 simultaneous requests with DIFFERENT reference voices, and reports wall time, batch sizes, whether
/health keeps answering while the worker is busy, GPU memory, and (if librosa is installed) whether each clip's pitch is
close to what the same voice gets when generated alone, which shows the right voice went to the right request."""
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import numpy as np
import requests
import soundfile as sf

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8766"
REFS = Path(sys.argv[2] if len(sys.argv) > 2 else "D:/clone_detection_tests/data/refs")
VOICES = ["aryan_app", "ashwini_app", "sobiya_app", "pallavi_app"]
TEXT = "Hello everyone! I'm here in Hyderabad, India, attending the Ruby Conference today. Looking forward to an amazing experience!"
OUT = Path(tempfile.mkdtemp(prefix="qwen_live_"))


def vram():
    try:
        return int(subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.split()[0])
    except Exception:  # noqa: BLE001
        return 0


def clone(voice, tag):
    ref = REFS / f"{voice}.wav"
    out = OUT / f"{tag}_{voice}.wav"
    r = requests.post(URL + "/clone", json={"ref": ref.as_posix(), "ref_text": (REFS / f"{voice}.txt").read_text(encoding="utf-8").strip(),
                                            "text": TEXT, "out": out.as_posix()}, timeout=600)
    return r.json(), out


def f0(path):
    try:
        import librosa
        y, sr = sf.read(str(path), dtype="float32")
        f = librosa.yin(y if y.ndim == 1 else y.mean(axis=1), fmin=70, fmax=400, sr=sr)
        return float(np.median(f))
    except ImportError:
        return None


print("health:", requests.get(URL + "/health", timeout=5).json())
base = {}
for v in VOICES:
    res, out = clone(v, "alone")
    base[v] = f0(out)
    print(f"  alone  {v:12s} {res['seconds']:5.1f} s   median pitch {base[v] and round(base[v])} Hz")

base_mem = vram()
for n in (1, 2, 4, 6):
    voices = [VOICES[i % len(VOICES)] for i in range(n)]
    results, health_ms, peak = {}, [], [base_mem]
    stop = threading.Event()

    def watch():
        while not stop.is_set():
            t = time.time()
            try:
                requests.get(URL + "/health", timeout=3)
                health_ms.append(round(1000 * (time.time() - t)))
            except requests.RequestException:
                health_ms.append(-1)
            peak.append(vram())
            time.sleep(1.0)

    def go(i, v):
        results[i] = clone(v, f"n{n}_{i}")
    w = threading.Thread(target=watch); w.start()
    t0 = time.time()
    ts = [threading.Thread(target=go, args=(i, v)) for i, v in enumerate(voices)]
    for t in ts:
        t.start()
        time.sleep(0.05)
    [t.join() for t in ts]
    wall = time.time() - t0
    stop.set(); w.join()
    sizes = sorted({r[0].get("batch_size") for r in results.values()})
    ok = all(r[0].get("ok") for r in results.values())
    drift = []
    for i, v in enumerate(voices):
        a, b = f0(results[i][1]), base[v]
        if a and b:
            drift.append(round(100 * (a - b) / b))
    print(f"{n} at once: wall {wall:5.1f} s ({wall/n:4.1f} s per clip), batch sizes {sizes}, all ok: {ok}, "
          f"/health answered in {max(health_ms)} ms at worst ({health_ms.count(-1)} misses), GPU +{max(peak) - base_mem} MiB, pitch vs alone {drift} %")
print("health after:", requests.get(URL + "/health", timeout=5).json()["batching"])
print("clips in", OUT)
