"""Clone-spotting demo: API + the static page.   Run:  python -m uvicorn server:app --port 8000   (see start_demo.ps1)

Phase 1 (this file): consent -> recording -> clones made by every engine -> status.
Not built yet: the four-card listening game, the pick, and the reveal with the clone-check scores.
"""
import logging
import os
import shutil
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import audio
import config
import engines
import game
import pipeline
import scoring
import store
from consent import CONSENT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("server")
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
DEBUG = os.environ.get("DEMO_DEBUG") == "1"


@asynccontextmanager
async def lifespan(_app):
    config.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    scoring.warm_up()          # loads the 1.2 GB clone-check model in the background so the reveal is quick
    n = store.purge_unconsented()
    if n:
        log.info("purged %d old sessions without retention consent", n)
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
        audio.write_wav(d / "original.wav", x)
        store.write(sid, "recording.json", {**verdict, "browser_sample_rate": sr, "at": time.time()})
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


@app.post("/api/sessions/{sid}/finish")
def finish(sid: str):
    """Called when the participant is done. Deletes everything unless they ticked the retention box."""
    _need(sid)
    if store.read(sid, "consent.json", {}).get("retain"):
        return {"deleted": False}
    store.delete(sid)
    return {"deleted": True}


@app.delete("/api/sessions/{sid}")
def delete_session(sid: str):
    """The participant (or the host) asks for the data to be removed, retention consent or not."""
    _need(sid)
    store.delete(sid)
    return {"deleted": True}


@app.get("/api/health")
def health():
    """For the person running the demo: is every engine ready? (Shows engine names; keep this off the participant's screen.)"""
    out = {}
    for e in engines.enabled():
        ok, why = e.available()
        out[e.name] = {"ready": ok, "reason": why}
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
