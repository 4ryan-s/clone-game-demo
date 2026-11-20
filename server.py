"""Clone-spotting demo: API + the static page.   Run:  python -m uvicorn server:app --port 8000   (see start_demo.ps1)

Consent -> recording -> clones made by every engine -> cards, pick and reveal with the clone-check scores.
Data: a session folder is working data and is deleted when the session ends. A recording is kept (numbered, with its
session id) in data/voice_samples/ only if the participant ticked the optional box (see voicebank.py).
"""
import asyncio
import html
import logging
import os
import shutil
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import audio
import config
import engines
import game
import logsetup
import pipeline
import scoring
import shares
import speech_check
import stats
import store
import voicebank
from consent import CONSENT

logsetup.setup()
log = logging.getLogger("server")
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
DEBUG = os.environ.get("DEMO_DEBUG") == "1"


def _watch_workers() -> None:
    """After a (re)start, say once for every Qwen worker whether it is ready, so a worker that never came up shows in the log."""
    import requests
    pending = set(config.QWEN_URLS)
    for _ in range(60):                                          # up to about 5 minutes: the model takes a while to load
        for url in sorted(pending):
            try:
                r = requests.get(url + "/health", timeout=3)
                if r.ok and r.json().get("ready"):
                    h = r.json()
                    log.info("qwen worker %s is ready: %s %s, batching %s", url, h.get("device"), h.get("dtype"), h.get("batching"))
                    pending.discard(url)
            except requests.RequestException:
                pass
        if not pending:
            return
        time.sleep(5)
    log.warning("qwen worker(s) still not ready after 5 minutes: %s", sorted(pending))


@asynccontextmanager
async def lifespan(_app):
    config.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    scoring.warm_up()          # loads the 1.2 GB clone-check model in the background so the reveal is quick
    n = store.purge_stale()
    if n:
        log.info("removed %d unfinished working sessions older than 24 h", n)
    m = shares.purge_old()
    if m:
        log.info("removed %d share images older than %s days", m, config.SHARE_RETENTION_DAYS)
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
    cloning: bool = False
    version: str


@app.post("/api/sessions")
def create_session(body: ConsentIn):
    if not body.agree or not body.cloning:
        raise HTTPException(400, "The required agreement was not given")
    if body.version != config.CONSENT_VERSION:
        raise HTTPException(409, "The consent wording changed. Please reload the page and read it again.")
    sid = store.new_id()
    store.write(sid, "consent.json", {"agree": True, "cloning": True, "retain": body.retain, "version": body.version,
                                      "at": time.time(), "at_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
    return {"session_id": sid}


@app.post("/api/sessions/{sid}/recording")
async def upload_recording(sid: str, file: UploadFile = File(...)):
    _need(sid)
    t_upload = time.time()
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
    review = None
    if verdict["ok"]:
        # Words, hesitation sounds and long pauses. Runs in a thread: it calls Sarvam and the speech detector, which must not block the server.
        review = await asyncio.to_thread(speech_check.review, x)
        verdict["issues"] += review["issues"]
        verdict["ok"] = not verdict["issues"]
        verdict["transcript"] = review["transcript"]
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
                number = voicebank.save(sid, d / "original.wav", consent.get("version", ""), verdict["seconds"], verdict.get("transcript") or "")
                log.info("session %s voice sample saved as #%06d", sid, number)
            except OSError as exc:
                log.error("could not save the voice sample for %s: %s", sid, exc)
                raise HTTPException(500, "Your recording could not be saved. Please try again.")
        for stale in ("clones", "raw", "meta.json"):          # a re-record starts the clones over
            p = d / stale
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.exists():
                p.unlink()
    # Numbers only: never the transcript or the audio.
    words = len((verdict.get("transcript") or "").split())
    log.info("session %s recording %s in %.1fs: %.1fs long, level %s dBFS, clipped %s, speech-to-text %s, %d words, speech %ss, longest pause %ss, "
             "snr %s dB, fillers %d, issues %d%s",
             sid, "accepted" if verdict["ok"] else "REJECTED", time.time() - t_upload, verdict.get("seconds", 0), verdict.get("level_dbfs"),
             verdict.get("clipped_fraction"), "not run" if review is None else ("failed" if review["stt_error"] else "ok"), words,
             review and review["speech_seconds"], review and review["longest_pause"], review and review["snr_db"],
             len(review["fillers"]) if review else 0, len(verdict["issues"]),
             f", stt error: {review['stt_error']}" if review and review["stt_error"] else "")
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
    card = game.find_card(sid, body.card)
    if not card:
        raise HTTPException(404, "Unknown card")
    t0 = time.time()
    result = game.pick(sid, body.card)
    log.info("session %s pick: chose the %s%s -> %s; reveal (clone check on %d clips) took %.2fs on %s", sid,
             "real recording" if card["kind"] == "real" else "clone from ", "" if card["kind"] == "real" else card["engine"],
             "WON" if result["won"] else "lost", len(result["cards"]), time.time() - t0, scoring.device() or "?")
    return result


@app.post("/api/sessions/{sid}/finish")
def finish(sid: str):
    """Called when the participant is done. The working session (clones, scores, everything but the voice bank) is always
    deleted. `kept` says whether their own recording stays in the voice bank because they agreed to that."""
    _need(sid)
    kept = bool(store.read(sid, "consent.json", {}).get("retain"))
    store.delete(sid)
    log.info("session %s finished: working files deleted, voice sample %s", sid, "kept (participant agreed)" if kept else "not kept")
    return {"deleted": not kept, "kept": kept}


@app.delete("/api/sessions/{sid}")
def delete_session(sid: str):
    """The participant (or the host) asks for their data to be removed, using the session code. Removes the working
    session if it still exists and the saved recording in the voice bank. Works after Finish too."""
    if not store.valid_id(sid):
        raise HTTPException(404, "Unknown session code")
    had_session = store.exists(sid)
    removed = voicebank.delete_for_session(sid)
    shared = shares.delete_for_session(sid)
    if not had_session and not removed and not shared:
        raise HTTPException(404, "Unknown session code")
    store.delete(sid)
    return {"deleted": True, "sample_deleted": bool(removed), "share_deleted": bool(shared)}


# ------------------------------------------------------------- share picture for a phone (QR code on the Share card)
class ShareIn(BaseModel):
    image: str = ""          # the finished share picture as a PNG data URL, drawn in the browser


@app.post("/api/sessions/{sid}/share")
def upload_share(sid: str, body: ShareIn):
    """Keep the share picture for a few days and return the link the QR code points to. Nothing personal is stored."""
    _need(sid)
    shares.purge_old()
    token = shares.save(sid, body.image)
    if not token:
        raise HTTPException(400, "The image was missing or not a valid PNG")
    return {"ok": True, "token": token, "url": f"{config.PUBLIC_BASE_URL}/s/{token}" if config.PUBLIC_BASE_URL else f"/s/{token}"}


@app.get("/api/shares/{token}.png")
def share_image(token: str):
    path = shares.image_path(token)
    if not path:
        raise HTTPException(404, "Not found")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff"})


_SHARE_PAGE = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Real or Clone</title>
<style>
  body { margin:0; min-height:100vh; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:18px; padding:24px;
         background:#1d0a0e; color:#f3e9d8; font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }
  h1 { font-size:22px; margin:0; text-align:center; }
  p { margin:0; color:#c8b8a4; text-align:center; }
  img { width:100%; max-width:520px; height:auto; border-radius:12px; }
  .row { display:flex; gap:12px; flex-wrap:wrap; justify-content:center; }
  a.btn, button.btn { appearance:none; cursor:pointer; text-decoration:none; font-size:16px; font-weight:600; padding:14px 26px; border-radius:999px; border:1px solid #d8a94a; }
  .primary { background:#d8a94a; color:#1a0a0d; }
  .ghost { background:transparent; color:#f3e9d8; }
</style></head><body>
  <h1>Your image is ready</h1>
  __NOTE__
  <img src="__IMG__" alt="Your image to share">
  <div class="row">
    <button class="btn primary" id="share" type="button">Share</button>
    <a class="btn ghost" href="__IMG__" download="real-or-clone-share.png">Download</a>
  </div>
<script>
  var url = "__IMG__";
  var caption = "#RCI26 #RCI @joshsoftware";
  var ready = fetch(url).then(function (r) { return r.blob(); });
  document.getElementById("share").addEventListener("click", async function () {
    try {
      var blob = await ready;
      var file = new File([blob], "real-or-clone-share.png", { type: "image/png" });
      var withCaption = { files: [file], text: caption };
      if (navigator.canShare && navigator.canShare(withCaption)) { await navigator.share(withCaption); }
      else if (navigator.canShare && navigator.canShare({ files: [file] })) { await navigator.share({ files: [file] }); }
      else { window.location.href = url; }
    } catch (e) {}
  });
</script></body></html>"""


@app.get("/s/{token}", response_class=HTMLResponse)
def share_page(token: str):
    """The page the QR code opens on a phone: the picture with Download and Share buttons."""
    if not shares.image_path(token):
        raise HTTPException(404, "This image is no longer available")
    note = f"<p>{html.escape(config.SHARE_BOOTH_NOTE)}</p>" if config.SHARE_BOOTH_NOTE else ""
    page = _SHARE_PAGE.replace("__IMG__", f"/api/shares/{token}.png").replace("__NOTE__", note)
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})


@app.get("/api/stats")
def public_stats():
    """Totals for the booth board. Written when a player locks in a choice, before they press Finish."""
    return JSONResponse(
        {**stats.snapshot(), "saved": voicebank.count_saved()},
        headers={"Cache-Control": "no-store"},
    )


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


@app.get("/dashboard")
@app.get("/dashboard/")
def dashboard_page():
    """The big-screen booth board. The React app reads the path and renders the live stats."""
    index = _DIST / "index.html"
    if not index.is_file():
        raise HTTPException(404, "The dashboard is not built yet")
    return FileResponse(index, headers={"Cache-Control": "no-cache"})


# The React quiz (frontend/, built into frontend/dist) is the demo page. The first plain-HTML page stays at /classic as a fallback.
app.mount("/classic", StaticFiles(directory=config.ROOT / "static", html=True), name="classic")
_DIST = config.ROOT / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="quiz")
else:
    log.warning("frontend/dist is missing: run `python setup.py --only frontend` (or `cd frontend && npm install && npm run build`). Serving the classic page at / instead.")
    app.mount("/", StaticFiles(directory=config.ROOT / "static", html=True), name="static")
