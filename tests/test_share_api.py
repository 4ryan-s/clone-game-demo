"""API checks for the share picture routes (upload, phone page, image, delete), in a temporary folder.   python tests/test_share_api.py"""
import base64
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

config.SHARES_DIR = Path(tempfile.mkdtemp(prefix="share_api_test_")) / "shares"
config.PUBLIC_BASE_URL = "http://booth.example"

from fastapi.testclient import TestClient  # noqa: E402
import server  # noqa: E402

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==")
URL = "data:image/png;base64," + base64.b64encode(PNG).decode()


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        sys.exit(1)


client = TestClient(server.app)   # no `with`: skips startup (models) so this stays fast
r = client.post("/api/sessions", json={"agree": True, "cloning": True, "retain": False, "version": config.CONSENT_VERSION})
sid = r.json().get("session_id")
check(r.status_code == 200 and sid, f"a session can be created ({sid})")

r = client.post(f"/api/sessions/{sid}/share", json={"image": "data:image/png;base64,AAAA"})
check(r.status_code == 400, f"a non-PNG upload is refused (got {r.status_code})")
r = client.post(f"/api/sessions/nosuchsession/share", json={"image": URL})
check(r.status_code == 404, f"an unknown session is refused (got {r.status_code})")

r = client.post(f"/api/sessions/{sid}/share", json={"image": URL})
check(r.status_code == 200 and r.json()["ok"], "a valid picture is accepted")
url = r.json()["url"]
check(url.startswith("http://booth.example/s/"), f"the link uses PUBLIC_BASE_URL: {url}")
token = url.rsplit("/", 1)[1]

r = client.get(f"/s/{token}")
check(r.status_code == 200 and "text/html" in r.headers["content-type"] and f"/api/shares/{token}.png" in r.text, "the phone page loads and points at the image")
r = client.get(f"/api/shares/{token}.png")
check(r.status_code == 200 and r.content == PNG and r.headers["content-type"] == "image/png", "the image downloads as a PNG")
check(client.get("/s/doesnotexist").status_code == 404 and client.get("/api/shares/doesnotexist.png").status_code == 404, "unknown tokens give 404")

r = client.delete(f"/api/sessions/{sid}")
check(r.status_code == 200 and r.json().get("share_deleted") == 1, f"deleting the session reports the share removed: {r.json()}")
check(client.get(f"/api/shares/{token}.png").status_code == 404 and client.get(f"/s/{token}").status_code == 404, "after deletion the QR link no longer works")
print("ALL PASSED")
