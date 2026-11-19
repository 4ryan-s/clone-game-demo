"""Saved voice samples: the original recordings of participants who ticked the optional "keep my recording" box.

    data/voice_samples/000000.wav, 000001.wav, ...   one file per participant, numbered from 0 and never renumbered
    data/voice_samples/index.csv                      index, session_id, status, times, consent version, length, checksum

The folder is inside the repository folder but under data/, which git ignores: recordings are never committed or pushed.
A participant who did not tick the box never gets a file here (their working recording is deleted when the session ends).
The session id is stored with every sample so the person can ask for it to be deleted. A deleted sample keeps its row
(status "deleted", no file) so its number is never given to someone else.

Command line (for the person running the demo):
    python voicebank.py list
    python voicebank.py delete <session_id>
"""
import csv
import hashlib
import os
import shutil
import sys
import threading
import time
from pathlib import Path

import config

FIELDS = ["index", "session_id", "status", "saved_at", "updated_at", "consent_version", "seconds", "sha256", "deleted_at"]
_lock = threading.RLock()   # one server process; the index is small and rewritten whole under this lock


def _dir() -> Path:
    return Path(config.VOICE_SAMPLES_DIR)


def _index_path() -> Path:
    return _dir() / "index.csv"


def _file(index: int) -> Path:
    return _dir() / f"{index:06d}.wav"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _read() -> list[dict]:
    p = _index_path()
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _write(rows: list[dict]) -> None:
    p = _index_path()
    tmp = p.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, p)


def _next_index(rows: list[dict]) -> int:
    """One more than the highest number ever used: counted from the index rows and from any wav file already in the folder."""
    used = [int(r["index"]) for r in rows]
    used += [int(f.stem) for f in _dir().glob("[0-9][0-9][0-9][0-9][0-9][0-9].wav")]
    return max(used, default=-1) + 1


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save(session_id: str, wav_path: Path, consent_version: str, seconds: float) -> int:
    """Copy the recording into the numbered folder and return its number.
    Called only when the participant agreed to keep their recording. A second call for the same session (they recorded
    again) replaces the file under the same number."""
    with _lock:
        _dir().mkdir(parents=True, exist_ok=True)
        rows = _read()
        row = next((r for r in rows if r["session_id"] == session_id and r["status"] == "saved"), None)
        index = int(row["index"]) if row else _next_index(rows)
        dest = _file(index)
        tmp = dest.with_suffix(".wav.tmp")
        shutil.copyfile(wav_path, tmp)
        os.replace(tmp, dest)
        fields = {"seconds": f"{seconds:.2f}", "sha256": _sha256(dest), "updated_at": _now(), "consent_version": consent_version}
        if row:
            row.update(fields)
        else:
            rows.append({"index": index, "session_id": session_id, "status": "saved", "saved_at": _now(), "deleted_at": "", **fields})
        _write(rows)
        return index


def delete_for_session(session_id: str) -> list[int]:
    """Delete the saved recording of this session (the file goes, the row stays marked deleted). Returns the numbers removed."""
    removed = []
    with _lock:
        rows = _read()
        for r in rows:
            if r["session_id"] == session_id and r["status"] == "saved":
                _file(int(r["index"])).unlink(missing_ok=True)
                r["status"] = "deleted"
                r["deleted_at"] = _now()
                removed.append(int(r["index"]))
        if removed:
            _write(rows)
    return removed


def find(session_id: str) -> list[dict]:
    with _lock:
        return [r for r in _read() if r["session_id"] == session_id]


def count_saved() -> int:
    """How many recordings are currently kept in the voice bank (not counting deleted ones)."""
    with _lock:
        return sum(r["status"] == "saved" for r in _read())


def _main(argv: list[str]) -> int:
    if argv[:1] == ["list"]:
        rows = _read()
        for r in rows:
            print(f"{int(r['index']):06d}  {r['status']:8s}  {r['session_id']:14s}  {r['seconds']:>6s}s  {r['saved_at']}")
        print(f"{sum(r['status'] == 'saved' for r in rows)} saved, {sum(r['status'] == 'deleted' for r in rows)} deleted")
        return 0
    if len(argv) == 2 and argv[0] == "delete":
        removed = delete_for_session(argv[1])
        print(f"deleted samples {removed}" if removed else "no saved sample for that session code")
        return 0 if removed else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
