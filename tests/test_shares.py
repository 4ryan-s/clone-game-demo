"""Checks for shares.py (the share picture kept for the QR code), in a temporary folder.   python tests/test_shares.py"""
import base64
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import shares  # noqa: E402

config.SHARES_DIR = Path(tempfile.mkdtemp(prefix="shares_test_")) / "shares"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==")   # a 1x1 PNG
URL = "data:image/png;base64," + base64.b64encode(PNG).decode()


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        sys.exit(1)


check(shares.save("sessAAAAAA", "not a data url") is None, "text that is not an image is refused")
check(shares.save("sessAAAAAA", "data:image/png;base64," + base64.b64encode(b"<html>not a png</html>").decode()) is None, "a file that is not a PNG is refused")
check(shares.save("sessAAAAAA", "data:image/png;base64,@@@") is None, "broken base64 is refused")
check(not config.SHARES_DIR.exists(), "nothing is written for refused images")

t1 = shares.save("sessAAAAAA", URL)
check(t1 and shares.image_path(t1).read_bytes() == PNG, "a valid PNG is saved and can be read back")
meta = json.loads((config.SHARES_DIR / f"{t1}.json").read_text(encoding="utf-8"))
check(set(meta) == {"session_id", "at"}, f"only the session code and time are stored beside it: {sorted(meta)}")
check(shares.save("sessAAAAAA", URL) == t1, "the same session gets the same token again, so a QR already scanned stays valid")
t2 = shares.save("sessBBBBBB", URL)
check(t2 and t2 != t1, "another session gets its own token")
check(shares.image_path("../etc/passwd") is None and shares.image_path("nope") is None, "unknown or odd tokens find nothing")

check(shares.delete_for_session("sessAAAAAA") == 1 and shares.image_path(t1) is None, "deleting by session code removes the image")
check(not (config.SHARES_DIR / f"{t1}.json").exists(), "and its small record too")
check(shares.delete_for_session("sessAAAAAA") == 0 and shares.delete_for_session("nobody") == 0, "deleting twice or an unknown session removes nothing")
check(shares.image_path(t2) is not None, "the other session's image is untouched")

(config.SHARES_DIR / f"{t2}.json").write_text(json.dumps({"session_id": "sessBBBBBB", "at": time.time() - 10 * 86400}), encoding="utf-8")
t3 = shares.save("sessCCCCCC", URL)
check(shares.purge_old(7) == 1, "images older than the retention are purged")
check(shares.image_path(t2) is None and shares.image_path(t3) is not None, "the old one is gone and the recent one stays")
print("ALL PASSED")
