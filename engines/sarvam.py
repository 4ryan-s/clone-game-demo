"""Sarvam voice cloning over the internet (POST /voices/clone).

The key comes from the SARVAM_API_KEY environment variable (or the Windows user settings). It is never logged,
never written to disk, and scrubbed from any error text.
"""
import base64
import logging
import os
import threading
import time
from collections import deque
from pathlib import Path

import requests

import config
from .base import Engine, EngineError

log = logging.getLogger("engine.sarvam")


class _Meter:
    """Counts the HTTP requests made to Sarvam (across both Sarvam clones, which share one rate limit).
    Keeps the timestamps of the last hour so it can report a rolling per-minute and per-hour rate."""

    def __init__(self):
        self._lock = threading.Lock()
        self._total = 0
        self._times = deque()   # request timestamps within the last hour

    def hit(self) -> None:
        now = time.time()
        with self._lock:
            self._total += 1
            total = self._total
            self._times.append(now)
            while self._times and now - self._times[0] > 3600:
                self._times.popleft()
            per_hour = len(self._times)
            per_min = sum(1 for t in self._times if now - t <= 60)
        log.info("Sarvam request #%d sent (last 1 min: %d, last 1 hr: %d)", total, per_min, per_hour)


_meter = _Meter()


def _key() -> str | None:
    key = os.environ.get("SARVAM_API_KEY")
    if not key and os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as handle:
                key = winreg.QueryValueEx(handle, "SARVAM_API_KEY")[0]
        except OSError:
            key = None
    return key.strip() if key else None


class Sarvam(Engine):
    name = "sarvam"
    lock_group = "sarvam"      # both Sarvam clones share one remote rate limit, so they must not fire at the same time
    params: dict = {}          # extra form fields for /voices/clone; the variant below overrides these

    def available(self):
        return (True, "") if _key() else (False, "SARVAM_API_KEY is not set")

    def clone(self, ref_wav: Path, ref_text: str, text: str, out_wav: Path) -> dict:
        key = _key()
        if not key:
            raise EngineError("SARVAM_API_KEY is not set")
        r = self._post(ref_wav, ref_text, text, key)
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        out_wav.write_bytes(base64.b64decode(r.json()["audio"]))
        return {"service": "sarvam", "params": dict(self.params)}

    def _post(self, ref_wav: Path, ref_text: str, text: str, key: str):
        """POST to Sarvam, retrying a 429 (rate limit) a few times with backoff before giving up."""
        last = None
        for attempt in range(config.SARVAM_MAX_RETRIES + 1):
            _meter.hit()
            try:
                with open(ref_wav, "rb") as fh:
                    r = requests.post(
                        "https://api.sarvam.ai/voices/clone", headers={"api-subscription-key": key},
                        files={"ref_audio": ("ref.wav", fh, "audio/wav")},
                        data={"text": text, "language_code": "en-IN", "ref_text": ref_text, **self.params},
                        timeout=config.SARVAM_TIMEOUT_S)
            except requests.RequestException as exc:
                raise EngineError(f"Sarvam request failed ({type(exc).__name__})") from None
            if r.status_code == 200:
                return r
            last = EngineError(f"Sarvam HTTP {r.status_code}: {r.text[:200].replace(key, '<key>')}")
            if r.status_code != 429 or attempt == config.SARVAM_MAX_RETRIES:
                raise last
            delay = self._retry_delay(r, attempt)
            log.warning("Sarvam rate limited (429); retrying in %.1fs (attempt %d/%d)", delay, attempt + 1, config.SARVAM_MAX_RETRIES)
            time.sleep(delay)
        raise last  # pragma: no cover

    @staticmethod
    def _retry_delay(r, attempt: int) -> float:
        """Honour a Retry-After header if the server sent one, otherwise exponential backoff."""
        header = r.headers.get("Retry-After")
        if header:
            try:
                return max(0.0, float(header))
            except ValueError:
                pass
        return config.SARVAM_RETRY_BASE_S * (2 ** attempt)


class SarvamVariant(Sarvam):
    """The same Sarvam cloning service with different settings (config.SARVAM_VARIANT_PARAMS), for a second, slightly different clone."""
    name = "sarvam2"
    params = config.SARVAM_VARIANT_PARAMS
