"""Running totals for the consent page. Sessions are deleted at the end, so the counts live here.

data/stats.json
    guests       people who picked a voice
    identified   of those, people who picked their own voice
    missed       of those, people who picked a clone
    voices       real recordings plus clones that were in those rounds
"""
import json
import threading

import config

_lock = threading.Lock()
_PATH = config.ROOT / "data" / "stats.json"
_EMPTY = {"guests": 0, "identified": 0, "missed": 0, "voices": 0}


def snapshot() -> dict:
    with _lock:
        return dict(_read())


def record_attempt(won: bool, voices: int) -> None:
    """Count one finished guess. Call once, the first time that session picks."""
    with _lock:
        stats = _read()
        stats["guests"] += 1
        stats["identified" if won else "missed"] += 1
        stats["voices"] += max(0, int(voices))
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(stats), encoding="utf-8")
        tmp.replace(_PATH)


def _read() -> dict:
    if not _PATH.is_file():
        return dict(_EMPTY)
    try:
        raw = json.loads(_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(_EMPTY)
    return {key: int(raw.get(key, 0) or 0) for key in _EMPTY}
