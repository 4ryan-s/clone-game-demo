"""End-to-end check of phase 1 against a running server: consent -> bad recording rejected -> good recording ->
clones from every engine -> status -> files on disk -> finish/delete.   python tests/smoke_api.py <reference.wav> [base_url]
Needs DEMO_DEBUG=1 on the server only for the optional file fetch at the end.
Note: it saves (then deletes) one sample in data/voice_samples/, so it uses up sample number 0 of that folder.
Run it before real participants, then delete data/voice_samples/ so real numbering starts at 0; never run it on a live server."""
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

mid = len(x) // 2
gapped = np.concatenate([x[:mid], np.zeros(int(2.8 * sr), dtype=np.float32), x[mid:]])
v = requests.post(f"{base}/api/sessions/{sid}/recording", files={"file": ("r.wav", wav_bytes(gapped, sr), "audio/wav")}).json()
check(not v["ok"] and any("pause" in i for i in v["issues"]), f"a 2.8 s pause in the middle is sent back: {v['issues']}")
if len(sys.argv) > 3:       # optional: a recording with "um" / "uh" in it (for example Sarvam text-to-speech saying them)
    fx, fsr = sf.read(sys.argv[3], dtype="float32")
    v = requests.post(f"{base}/api/sessions/{sid}/recording", files={"file": ("r.wav", wav_bytes(fx if fx.ndim == 1 else fx.mean(axis=1), fsr), "audio/wav")}).json()
    check(not v["ok"] and any("hesitation" in i for i in v["issues"]), f"a recording with um / uh is sent back: {v['issues']}")

v = requests.post(f"{base}/api/sessions/{sid}/recording", files={"file": ("r.wav", wav_bytes(x, sr), "audio/wav")}).json()
check(v["ok"], f"good recording accepted ({v['seconds']} s, {v['level_dbfs']} dBFS)")
check(bool(v.get("transcript")), f"words found by speech to text: {v.get('transcript')!r}")
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

bank = os.path.join(os.path.dirname(d), "..", "voice_samples")


def bank_rows():
    import csv
    p = os.path.join(bank, "index.csv")
    return list(csv.DictReader(open(p, newline="", encoding="utf-8"))) if os.path.exists(p) else []


mine = [r for r in bank_rows() if r["session_id"] == sid]
check(len(mine) == 1 and mine[0]["status"] == "saved", f"consented recording was saved as sample number {mine[0]['index'] if mine else '?'}")
sample = os.path.join(bank, f"{int(mine[0]['index']):06d}.wav")
check(os.path.isfile(sample) and sf.info(sample).samplerate == 16000, "numbered wav exists (16 kHz)")
fin = requests.post(f"{base}/api/sessions/{sid}/finish").json()
check(fin == {"deleted": False, "kept": True}, "finish: working session removed, recording kept because they agreed")
check(not os.path.exists(d) and os.path.isfile(sample), "session folder is gone, the saved sample is still there")
gone = requests.delete(f"{base}/api/sessions/{sid}").json()
check(gone["deleted"] and gone["sample_deleted"], "deletion by session code works after Finish and removes the sample")
check(not os.path.exists(sample) and [r["status"] for r in bank_rows() if r["session_id"] == sid] == ["deleted"], "file removed, index row marked deleted")
check(requests.delete(f"{base}/api/sessions/{sid}").status_code == 404, "deleting again says unknown session code")

# a participant who did NOT agree to keep their recording: nothing is saved anywhere, everything is deleted at Finish
before = len(bank_rows())
sid2 = requests.post(base + "/api/sessions", json={"agree": True, "retain": False, "version": cfg["consent"]["version"]}).json()["session_id"]
v2 = requests.post(f"{base}/api/sessions/{sid2}/recording", files={"file": ("r.wav", wav_bytes(x, sr), "audio/wav")}).json()
check(v2["ok"] and len(bank_rows()) == before and not any(r["session_id"] == sid2 for r in bank_rows()), "no consent: nothing added to the voice bank")
d2 = os.path.join(os.path.dirname(d), sid2)
check(os.path.isfile(os.path.join(d2, "original.wav")), "working copy exists while the session runs")
check(requests.post(f"{base}/api/sessions/{sid2}/finish").json() == {"deleted": True, "kept": False}, "finish: everything deleted")
check(not os.path.exists(d2) and len(bank_rows()) == before, "no consent: session folder gone, voice bank unchanged")
print("ALL PASSED")
