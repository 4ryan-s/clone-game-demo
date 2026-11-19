"""Clone-spotting demo: API + the static page.   Run:  python -m uvicorn server:app --port 8000   (see start_demo.ps1)

Consent -> recording -> clones made by every engine -> cards, pick and reveal with the clone-check scores.
Data: a session folder is working data and is deleted when the session ends. A recording is kept (numbered, with its
session id) in data/voice_samples/ only if the participant ticked the optional box (see voicebank.py).
"""
import base64
import json
import logging
import os
import re
import shutil
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import audio
import config
import engines
import game
import pipeline
import scoring
import stats
import store
import voicebank
from consent import CONSENT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("server")
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
DEBUG = os.environ.get("DEMO_DEBUG") == "1"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CERT_DIR = config.ROOT / "data" / "certificates"              # saved PNGs, kept after the session ends (for the QR)
CERTIFICATES_FILE = CERT_DIR / "log.jsonl"                    # one line per participant: who to send a goodie to
MAX_CERT_BYTES = 6 * 1024 * 1024
_cert_lock = threading.Lock()


def _save_certificate_png(token: str, data_url: str) -> bool:
    """Store the browser-made PNG under a token so a phone can fetch it later. Returns False if there was no valid image."""
    if not data_url.startswith("data:image/png"):
        return False
    try:
        raw = base64.b64decode(data_url.split(",", 1)[1], validate=True)
    except (ValueError, IndexError):
        return False
    if not raw or len(raw) > MAX_CERT_BYTES:
        return False
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    (CERT_DIR / f"{token}.png").write_bytes(raw)
    return True


@asynccontextmanager
async def lifespan(_app):
    config.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    scoring.warm_up()          # loads the 1.2 GB clone-check model in the background so the reveal is quick
    n = store.purge_stale()
    if n:
        log.info("removed %d unfinished working sessions older than 24 h", n)
    yield


app = FastAPI(title="Clone-spotting demo", lifespan=lifespan)


def _need(sid: str) -> None:
    if not store.exists(sid):
        raise HTTPException(404, "Unknown session")


@app.get("/api/config")
def get_config():
    return {"sentence": config.SENTENCE, "consent": CONSENT, "clone_count": len(engines.enabled()),
            "min_seconds": config.MIN_SECONDS, "max_seconds": config.MAX_SECONDS}


class ConsentIn(BaseModel):
    agree: bool
    retain: bool = False
    version: str


@app.post("/api/sessions")
def create_session(body: ConsentIn):
    if not body.agree:
        raise HTTPException(400, "The required agreement was not given")
    if body.version != config.CONSENT_VERSION:
        raise HTTPException(409, "The consent wording changed. Please reload the page and read it again.")
    sid = store.new_id()
    store.write(sid, "consent.json", {"agree": True, "retain": body.retain, "version": body.version, "at": time.time(),
                                      "at_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
    return {"session_id": sid}


@app.post("/api/sessions/{sid}/recording")
async def upload_recording(sid: str, file: UploadFile = File(...)):
    _need(sid)
    meta = store.read(sid, "meta.json", {})
    if meta.get("state") == "running":
        raise HTTPException(409, "Clones are being made. Wait for them to finish.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "That recording is too large")
    try:
        x, sr = audio.read_wav_bytes(data)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    x = audio.to_16k(x, sr)
    verdict = audio.check_recording(x)
    if verdict["ok"]:
        d = store.path(sid)
        first_recording = store.read(sid, "recording.json", None) is None   # re-records should not be counted again
        audio.write_wav(d / "original.wav", x)
        store.write(sid, "recording.json", {**verdict, "browser_sample_rate": sr, "at": time.time()})
        if first_recording:
            stats.record_recording()
        consent = store.read(sid, "consent.json", {})
        if consent.get("retain"):
            # Agreed to keep it: copy into the numbered voice bank now, so it is not lost if they close the tab before Finish.
            # A re-record replaces the earlier take under the same number. No agreement: nothing is copied anywhere.
            try:
                voicebank.save(sid, d / "original.wav", consent.get("version", ""), verdict["seconds"])
            except OSError as exc:
                log.error("could not save the voice sample for %s: %s", sid, exc)
                raise HTTPException(500, "Your recording could not be saved. Please try again.")
        for stale in ("clones", "raw", "meta.json"):          # a re-record starts the clones over
            p = d / stale
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.exists():
                p.unlink()
    return verdict


@app.post("/api/sessions/{sid}/generate")
def generate(sid: str):
    _need(sid)
    if not (store.path(sid) / "original.wav").exists():
        raise HTTPException(409, "Record the sentence first")
    meta = store.read(sid, "meta.json", {})
    if meta.get("state") in ("running", "done"):
        return {"state": meta["state"]}
    pipeline.start(sid)
    return {"state": "running"}


@app.get("/api/sessions/{sid}/status")
def status(sid: str):
    """What the browser may see: neutral slot ids and progress only. Engine names stay in meta.json."""
    _need(sid)
    meta = store.read(sid, "meta.json", {})
    clones = [{"slot": v["slot"], "status": v["status"], "seconds": v["seconds"]} for v in meta.get("engines", {}).values()]
    clones.sort(key=lambda c: c["slot"])
    return {"state": meta.get("state", "idle"), "clones": clones,
            "done": sum(c["status"] == "done" for c in clones), "total": len(engines.enabled())}


@app.get("/api/sessions/{sid}/cards")
def get_cards(sid: str):
    """Shuffled card ids only. Nothing here says which card is real."""
    _need(sid)
    if store.read(sid, "meta.json", {}).get("state") != "done":
        raise HTTPException(409, "The copies are not ready yet")
    return {"cards": game.make_cards(sid)}


@app.get("/api/sessions/{sid}/cards/{card}.wav")
def card_audio(sid: str, card: str):
    _need(sid)
    c = game.find_card(sid, card)
    if not c:
        raise HTTPException(404, "Unknown card")
    return Response(game.playback_wav(sid, c), media_type="audio/wav", headers={"Cache-Control": "no-store"})


class PickIn(BaseModel):
    card: str


@app.post("/api/sessions/{sid}/pick")
def pick(sid: str, body: PickIn):
    _need(sid)
    if not game.find_card(sid, body.card):
        raise HTTPException(404, "Unknown card")
    return game.pick(sid, body.card)


class CertificateIn(BaseModel):
    image: str = ""         # the finished certificate as a PNG data URL, made in the browser
    email: str = ""         # optional: so the booth can follow up
    name: str = ""
    won: bool = False


@app.post("/api/sessions/{sid}/certificate")
def certificate(sid: str, body: CertificateIn):
    """Save the browser-made certificate under a token and return a URL. On a shared kiosk the
    page shows this URL as a QR code so the participant can open it on their own phone."""
    _need(sid)
    email = body.email.strip()
    if email and not EMAIL_RE.match(email):
        raise HTTPException(400, "Enter a valid email address")
    token = store.new_id()
    if not _save_certificate_png(token, body.image):
        raise HTTPException(400, "The certificate image was missing or invalid")
    entry = {"token": token, "session_id": sid, "email": email, "name": body.name.strip()[:80],
             "won": bool(body.won), "at_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    with _cert_lock:
        CERT_DIR.mkdir(parents=True, exist_ok=True)
        with CERTIFICATES_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    store.write(sid, "certificate.json", {"token": token, "email": email, "name": entry["name"], "at": time.time()})
    # On a kiosk the phone cannot reach "localhost". Set PUBLIC_BASE_URL (for example the LAN IP or public
    # HTTPS host) and the QR will point there; otherwise the browser falls back to the page's own origin.
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    return {"ok": True, "token": token, "url": f"{base}/c/{token}" if base else f"/c/{token}"}


@app.get("/api/certificates/{token}.png")
def certificate_image(token: str):
    if not store.valid_id(token):
        raise HTTPException(404, "Certificate not found")
    f = CERT_DIR / f"{token}.png"
    if not f.is_file():
        raise HTTPException(404, "Certificate not found")
    return FileResponse(f, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/c/{token}", response_class=HTMLResponse)
def certificate_page(token: str):
    """Mobile-friendly page the QR points to: shows the certificate with a download/share button."""
    if not store.valid_id(token) or not (CERT_DIR / f"{token}.png").is_file():
        raise HTTPException(404, "Certificate not found")
    img = f"/api/certificates/{token}.png"
    html = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Your certificate</title>
<style>
  :root { color-scheme: light; }
  body { margin:0; min-height:100vh; display:flex; flex-direction:column; align-items:center; justify-content:center;
         gap:20px; padding:24px; background:#f3eee4; color:#1c1915;
         font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
  h1 { font-size:22px; margin:0; text-align:center; }
  p { margin:0; color:#6f685f; text-align:center; }
  img { width:100%; max-width:760px; height:auto; border-radius:16px;
        box-shadow:0 20px 50px -30px rgba(40,30,10,0.6); }
  .row { display:flex; gap:12px; flex-wrap:wrap; justify-content:center; }
  a.btn, button.btn { appearance:none; border:none; cursor:pointer; text-decoration:none;
        font-size:16px; font-weight:600; padding:14px 22px; border-radius:16px; }
  .primary { background:#0f6f5b; color:#fff; }
  .ghost { background:#fff; color:#1c1915; border:1px solid #e4dacb; }
</style></head><body>
  <h1>Your certificate is ready</h1>
  <p>Collect your goodie from the booth by showing this certificate.</p>
  <img id="cert" src="__IMG__" alt="Certificate">
  <div class="row">
    <a class="btn primary" href="__IMG__" download="voice-challenge-certificate.png">Download</a>
    <button class="btn ghost" id="share">Share</button>
  </div>
<script>
  var url = "__IMG__";
  document.getElementById("share").addEventListener("click", async function () {
    try {
      var res = await fetch(url); var blob = await res.blob();
      var file = new File([blob], "voice-challenge-certificate.png", { type: "image/png" });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], title: "Real or Clone \u2014 The Voice Challenge" });
      } else { window.location.href = url; }
    } catch (e) {}
  });
</script>
</body></html>"""
    return HTMLResponse(html.replace("__IMG__", img))


@app.post("/api/sessions/{sid}/finish")
def finish(sid: str):
    """Called when the participant is done. The working session (clones, scores, everything but the voice bank) is always
    deleted. `kept` says whether their own recording stays in the voice bank because they agreed to that."""
    _need(sid)
    kept = bool(store.read(sid, "consent.json", {}).get("retain"))
    store.delete(sid)
    return {"deleted": not kept, "kept": kept}


@app.delete("/api/sessions/{sid}")
def delete_session(sid: str):
    """The participant (or the host) asks for their data to be removed, using the session code. Removes the working
    session if it still exists and the saved recording in the voice bank. Works after Finish too."""
    if not store.valid_id(sid):
        raise HTTPException(404, "Unknown session code")
    had_session = store.exists(sid)
    removed = voicebank.delete_for_session(sid)
    if not had_session and not removed:
        raise HTTPException(404, "Unknown session code")
    store.delete(sid)
    return {"deleted": True, "sample_deleted": bool(removed)}


@app.get("/api/stats")
def public_stats():
    """Totals for the consent page: guests who have played, and the voices in those rounds."""
    return {**stats.snapshot(), "saved": voicebank.count_saved()}


@app.get("/api/health")
def health():
    """For the person running the demo: is every engine ready? (Shows engine names; keep this off the participant's screen.)"""
    out = {}
    for e in engines.enabled():
        ok, why = e.available()
        out[e.name] = {"ready": ok, "reason": why}
    ok, why = scoring.ready()
    out["spectra"] = {"ready": ok, "device": scoring.device(), "reason": why}
    return out


if DEBUG:
    @app.get("/api/dev/{sid}/{name:path}")
    def dev_file(sid: str, name: str):
        """Debug only (DEMO_DEBUG=1): fetch original.wav, clones/c1.wav, meta.json ..."""
        _need(sid)
        f = (store.path(sid) / name).resolve()
        if store.path(sid).resolve() not in f.parents or not f.is_file():
            raise HTTPException(404)
        return FileResponse(f)


# The React quiz (frontend/, built into frontend/dist) is the demo page. The first plain-HTML page stays at /classic as a fallback.
app.mount("/classic", StaticFiles(directory=config.ROOT / "static", html=True), name="classic")
_DIST = config.ROOT / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="quiz")
else:
    log.warning("frontend/dist is missing: run `python setup.py --only frontend` (or `cd frontend && npm install && npm run build`). Serving the classic page at / instead.")
    app.mount("/", StaticFiles(directory=config.ROOT / "static", html=True), name="static")
