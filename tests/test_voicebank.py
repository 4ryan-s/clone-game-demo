"""Unit checks for voicebank.py in a temporary folder.   python tests/test_voicebank.py"""
import csv
import sys
import tempfile
import threading
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import voicebank  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="voicebank_test_"))
config.VOICE_SAMPLES_DIR = tmp / "voice_samples"


def wav(name, seconds=1.0, value=0.1):
    p = tmp / name
    sf.write(str(p), np.full(int(16000 * seconds), value, dtype="float32"), 16000, subtype="PCM_16")
    return p


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        sys.exit(1)


def rows():
    with open(config.VOICE_SAMPLES_DIR / "index.csv", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


a, b, c = wav("a.wav", 1.0, 0.1), wav("b.wav", 2.0, 0.2), wav("c.wav", 3.0, 0.3)

check(not config.VOICE_SAMPLES_DIR.exists(), "nothing exists before the first consenting participant")
check(voicebank.save("sessAAAAAA", a, "draft-2", 1.0) == 0, "first sample is number 0")
check(voicebank.save("sessBBBBBB", b, "draft-2", 2.0) == 1, "second sample is number 1")
check((config.VOICE_SAMPLES_DIR / "000000.wav").is_file() and (config.VOICE_SAMPLES_DIR / "000001.wav").is_file(), "files are 000000.wav and 000001.wav")
check([r["session_id"] for r in rows()] == ["sessAAAAAA", "sessBBBBBB"], "index holds the session ids in order")

check(voicebank.save("sessAAAAAA", c, "draft-2", 3.0) == 0, "recording again keeps the same number")
data, _ = sf.read(str(config.VOICE_SAMPLES_DIR / "000000.wav"), dtype="float32")
check(abs(len(data) / 16000 - 3.0) < 0.01 and len(rows()) == 2, "the new take replaced the old file, no extra row")

check(voicebank.delete_for_session("sessAAAAAA") == [0], "delete by session id removes sample 0")
check(not (config.VOICE_SAMPLES_DIR / "000000.wav").exists(), "its file is gone")
r0 = rows()[0]
check(r0["status"] == "deleted" and r0["deleted_at"] != "" and r0["session_id"] == "sessAAAAAA", "its row stays, marked deleted")
check(voicebank.delete_for_session("sessAAAAAA") == [] and voicebank.delete_for_session("nobodyHERE") == [], "deleting twice or an unknown code removes nothing")
check(voicebank.save("sessCCCCCC", a, "draft-2", 1.0) == 2, "a deleted number is never reused")
check(voicebank.save("sessAAAAAA", a, "draft-2", 1.0) == 3, "someone who deleted and consents again gets a new number")

# two people finishing at once must get different numbers
out = []
threads = [threading.Thread(target=lambda i=i: out.append(voicebank.save(f"par{i:08d}", a, "draft-2", 1.0))) for i in range(20)]
[t.start() for t in threads]
[t.join() for t in threads]
check(sorted(out) == list(range(4, 24)), "20 saves at the same time got 20 distinct numbers")
check(len({r["index"] for r in rows()}) == len(rows()), "no duplicate numbers in the index")

# losing the index must not restart the numbering over existing files
(config.VOICE_SAMPLES_DIR / "index.csv").unlink()
check(voicebank.save("sessAfterLoss", a, "draft-2", 1.0) == 24, "numbering continues from the files on disk if the index is lost")
print("ALL PASSED")
