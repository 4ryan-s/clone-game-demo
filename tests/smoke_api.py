"""End-to-end check of phase 1 against a running server: consent -> bad recording rejected -> good recording ->
clones from every engine -> status -> files on disk -> finish/delete.   python tests/smoke_api.py <reference.wav> [base_url]
Needs DEMO_DEBUG=1 on the server only for the optional file fetch at the end."""
import io
import sys
import time

import numpy as np
import requests
import soundfile as sf

ref = sys.argv[1]
base = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000"


def wav_bytes(x, sr=16000):
    b = io.BytesIO(); sf.write(b, x, sr, format="WAV", subtype="PCM_16"); return b.getvalue()


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        sys.exit(1)


cfg = requests.get(base + "/api/config").json()
check(cfg["sentence"] and cfg["consent"]["version"], f"config ok, {cfg['clone_count']} engines")
print("health:", requests.get(base + "/api/health").json())

r = requests.post(base + "/api/sessions", json={"agree": False, "retain": False, "version": cfg["consent"]["version"]})
check(r.status_code == 400, "session refused without the required agreement")
r = requests.post(base + "/api/sessions", json={"agree": True, "retain": False, "version": "wrong"})
check(r.status_code == 409, "session refused on a stale consent version")
r = requests.post(base + "/api/sessions", json={"agree": True, "retain": True, "version": cfg["consent"]["version"]})
check(r.status_code == 200, "session created"); sid = r.json()["session_id"]

x, sr = sf.read(ref, dtype="float32")
x = x.mean(axis=1) if x.ndim > 1 else x
for name, clip, expect in (("too short", x[: 16000], "short"), ("silence", np.zeros(16000 * 5, np.float32), "quiet"),
                           ("clipped", np.clip(x[: 16000 * 5] * 80, -1, 1), "loud")):
    v = requests.post(f"{base}/api/sessions/{sid}/recording", files={"file": ("r.wav", wav_bytes(clip, sr), "audio/wav")}).json()
    check(not v["ok"] and any(expect in i for i in v["issues"]), f"{name} recording rejected: {v['issues']}")
check(requests.post(f"{base}/api/sessions/{sid}/generate").status_code == 409, "cannot generate before a good recording")
check(requests.post(f"{base}/api/sessions/{sid}/recording", files={"file": ("r.txt", b"not audio", "audio/wav")}).status_code == 400, "non-audio upload rejected")

v = requests.post(f"{base}/api/sessions/{sid}/recording", files={"file": ("r.wav", wav_bytes(x, sr), "audio/wav")}).json()
check(v["ok"], f"good recording accepted ({v['seconds']} s, {v['level_dbfs']} dBFS)")
t0 = time.time()
check(requests.post(f"{base}/api/sessions/{sid}/generate").json()["state"] == "running", "generation started")
while True:
    st = requests.get(f"{base}/api/sessions/{sid}/status").json()
    print(f"  {time.time() - t0:5.1f}s  {st['state']}  {[(c['slot'], c['status'], c['seconds']) for c in st['clones']]}")
    if st["state"] != "running":
        break
    if time.time() - t0 > 180:
        check(False, "generation finished within 180 s")
    time.sleep(2)
check(st["state"] == "done" and st["done"] == st["total"], f"all {st['total']} clones done in {time.time() - t0:.0f}s")
check("sarvam" not in str(st).lower() and "cosy" not in str(st).lower(), "status does not name any engine")

import os
d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sessions", sid)
for f in ["consent.json", "original.wav", "meta.json"] + [f"clones/c{i}.wav" for i in range(1, st["total"] + 1)]:
    check(os.path.isfile(os.path.join(d, f)), f"on disk: {f}")
for i in range(1, st["total"] + 1):
    info = sf.info(os.path.join(d, f"clones/c{i}.wav"))
    check(info.samplerate == 16000 and info.channels == 1 and info.duration > 1.5, f"c{i}.wav is 16 kHz mono, {info.duration:.1f} s")

check(requests.post(f"{base}/api/sessions/{sid}/finish").json()["deleted"] is False, "retention consent given: finish keeps the data")
check(requests.delete(f"{base}/api/sessions/{sid}").json()["deleted"], "explicit delete removes it")
check(not os.path.exists(d), "session folder is gone")
print("ALL PASSED")
