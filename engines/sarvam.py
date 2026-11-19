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

import audio
import config
import spectra_prep
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

    def _request(self, key: str, ref_wav: Path, ref_text: str, text: str, extra: dict) -> bytes:
        """One call to /voices/clone. Returns the WAV bytes."""
        r = None
        for attempt in range(3):                       # Sarvam answers 429 (rate limit) when many people clone at once: wait a little and retry
            try:
                with open(ref_wav, "rb") as fh:
                    r = requests.post(
                        "https://api.sarvam.ai/voices/clone", headers={"api-subscription-key": key},
                        files={"ref_audio": ("ref.wav", fh, "audio/wav")},
                        data={"text": text, "language_code": "en-IN", "ref_text": ref_text, **extra},
                        timeout=config.SARVAM_TIMEOUT_S)
            except requests.RequestException as exc:
                if attempt == 2:
                    raise EngineError(f"Sarvam request failed ({type(exc).__name__})") from None
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code == 429 or r.status_code >= 500:
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
            break
        if r.status_code != 200:
            raise EngineError(f"Sarvam HTTP {r.status_code}: {r.text[:200].replace(key, '<key>')}")
        return base64.b64decode(r.json()["audio"])

    @staticmethod
    def _span(wav_bytes: bytes) -> float:
        x, sr = audio.read_wav_bytes(wav_bytes)
        return spectra_prep.speech_span(audio.to_16k(x, sr))

    def clone(self, ref_wav: Path, ref_text: str, text: str, out_wav: Path) -> dict:
        key = _key()
        if not key:
            raise EngineError("SARVAM_API_KEY is not set")
        pace = float(self.params.get("pace", 1.0))
        data = self._request(key, ref_wav, ref_text, text, self.params)
        info = {"service": "sarvam", "params": dict(self.params), "pace": pace}
        # Match the speed of the original. Sarvam speaks at its own pace (slower than a fast speaker, and it adds pauses at punctuation), so
        # compare how long the clone's speech lasts with the original's. That only means something when both say the same words, which is the
        # case when the text is the transcript of the reference. If it is off by more than the tolerance, ask once more with a corrected pace.
        if config.SARVAM_MATCH_PACE and ref_text.strip().lower() == text.strip().lower():
            try:
                x, sr = audio.read_wav_bytes(Path(ref_wav).read_bytes())
                target = spectra_prep.speech_span(audio.to_16k(x, sr))
                got = self._span(data)
                ratio = got / target if target > 0 and got > 0 else 1.0
                info.update(target_s=round(target, 2), first_s=round(got, 2))
                if abs(ratio - 1.0) > config.SARVAM_PACE_TOLERANCE:
                    new_pace = min(config.SARVAM_PACE_MAX, max(config.SARVAM_PACE_MIN, pace * ratio))
                    if abs(new_pace - pace) > 0.02:
                        again = self._request(key, ref_wav, ref_text, text, {**self.params, "pace": f"{new_pace:.2f}"})
                        got2 = self._span(again)
                        if abs(got2 / target - 1.0) < abs(ratio - 1.0):          # keep whichever is closer to the original's speed
                            data, pace = again, new_pace
                            info.update(pace=round(pace, 2), matched_s=round(got2, 2))
            except Exception as exc:  # noqa: BLE001   (matching is an extra: never lose the clone because it failed)
                info["pace_match_error"] = f"{type(exc).__name__}: {str(exc)[:100]}"
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        out_wav.write_bytes(data)
        return info

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
