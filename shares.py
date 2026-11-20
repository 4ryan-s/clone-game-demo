"""Share images: the picture a winner posts, kept for a short time so a phone can fetch it by scanning the QR code on the Share card.

    data/shares/<token>.png   the PNG the browser drew (it shows the session code)
    data/shares/<token>.json  {"session_id": ..., "at": ...}  so it can be deleted with the participant's other data

No name, email or other personal detail is stored. One image per session (a second upload replaces the first and keeps the same
token, so a QR code already scanned stays valid). Images older than config.SHARE_RETENTION_DAYS are deleted; a participant who asks
for deletion with their session code (DELETE /api/sessions/<code>) has theirs deleted at once. data/ is git-ignored."""
import base64
import json
import os
import threading
import time
from pathlib import Path

import config
import store

MAX_BYTES = 6 * 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_lock = threading.Lock()


def _dir() -> Path:
    return Path(config.SHARES_DIR)


def _token_for(session_id: str) -> str | None:
    d = _dir()
    if not d.is_dir():
        return None
    for meta in d.glob("*.json"):
        try:
            if json.loads(meta.read_text(encoding="utf-8")).get("session_id") == session_id:
                return meta.stem
        except (OSError, ValueError):
            continue
    return None


def save(session_id: str, data_url: str) -> str | None:
    """Store the PNG (a data URL from the browser) and return its token, or None if it is not a valid PNG of a sensible size."""
    try:
        raw = base64.b64decode(data_url.split(",", 1)[1], validate=True)
    except Exception:  # noqa: BLE001
        return None
    if not raw.startswith(PNG_MAGIC) or len(raw) > MAX_BYTES:
        return None
    with _lock:
        d = _dir()
        d.mkdir(parents=True, exist_ok=True)
        token = _token_for(session_id) or store.new_id()
        tmp = d / f"{token}.png.tmp"
        tmp.write_bytes(raw)
        os.replace(tmp, d / f"{token}.png")
        (d / f"{token}.json").write_text(json.dumps({"session_id": session_id, "at": time.time()}), encoding="utf-8")
    return token


def image_path(token: str) -> Path | None:
    """The saved PNG for this token, or None (unknown token, or deleted)."""
    if not store.valid_id(token):
        return None
    p = _dir() / f"{token}.png"
    return p if p.is_file() else None


def delete_for_session(session_id: str) -> int:
    """Delete the share image of this session. Returns how many were removed (0 or 1)."""
    with _lock:
        token = _token_for(session_id)
        if not token:
            return 0
        for suffix in (".png", ".json"):
            (_dir() / f"{token}{suffix}").unlink(missing_ok=True)
        return 1


def purge_old(days: float | None = None) -> int:
    """Delete share images older than `days` (default config.SHARE_RETENTION_DAYS). Returns how many were removed."""
    days = config.SHARE_RETENTION_DAYS if days is None else days
    d = _dir()
    if not d.is_dir():
        return 0
    cutoff = time.time() - days * 86400
    removed = 0
    with _lock:
        for meta in d.glob("*.json"):
            try:
                at = json.loads(meta.read_text(encoding="utf-8")).get("at", 0)
            except (OSError, ValueError):
                at = 0
            if at < cutoff:
                (d / f"{meta.stem}.png").unlink(missing_ok=True)
                meta.unlink(missing_ok=True)
                removed += 1
    return removed
