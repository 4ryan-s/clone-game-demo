"""Where a session lives on disk:  data/sessions/<id>/
    consent.json   what the participant agreed to, which wording version, when
    original.wav   their recording, 16 kHz mono PCM16
    raw/<engine>.wav   what each engine produced, untouched (kept for later model training if consent allows)
    clones/<slot>.wav  the same clips at 16 kHz mono PCM16, which is what the game plays and scores
    meta.json      slot-to-engine mapping, timings, errors (never sent to the browser before the pick)
"""
import json
import re
import secrets
import shutil
import threading
import time
from pathlib import Path

import config

_ID = re.compile(r"^[A-Za-z0-9_-]{6,32}$")
_lock = threading.Lock()


def new_id() -> str:
    return secrets.token_urlsafe(8)


def valid_id(sid: str) -> bool:
    return bool(_ID.match(sid or ""))


def path(sid: str) -> Path:
    if not valid_id(sid):
        raise KeyError(sid)
    return config.SESSIONS_DIR / sid


def exists(sid: str) -> bool:
    return valid_id(sid) and path(sid).is_dir()


def read(sid: str, name: str, default=None):
    f = path(sid) / name
    if not f.exists():
        return default
    return json.loads(f.read_text(encoding="utf-8"))


def write(sid: str, name: str, obj) -> None:
    with _lock:
        f = path(sid) / name
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(f.suffix + ".tmp")
        tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
        tmp.replace(f)


def update_meta(sid: str, fn) -> dict:
    """Read-modify-write meta.json under one lock so parallel engines cannot overwrite each other."""
    with _lock:
        f = path(sid) / "meta.json"
        meta = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        fn(meta)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        tmp.replace(f)
        return meta


def delete(sid: str) -> None:
    if exists(sid):
        shutil.rmtree(path(sid), ignore_errors=True)


def purge_unconsented(max_age_hours: float = 24.0) -> int:
    """Delete sessions whose participant did not agree to retention and that are older than max_age_hours
    (for example when someone closed the tab before finishing). Returns how many were removed."""
    removed = 0
    if not config.SESSIONS_DIR.is_dir():
        return 0
    for d in config.SESSIONS_DIR.iterdir():
        try:
            consent = json.loads((d / "consent.json").read_text(encoding="utf-8")) if (d / "consent.json").exists() else {}
            if not consent.get("retain") and time.time() - d.stat().st_mtime > max_age_hours * 3600:
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
        except Exception:  # noqa: BLE001
            continue
    return removed
