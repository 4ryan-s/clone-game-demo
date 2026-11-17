"""Sarvam voice cloning over the internet (POST /voices/clone).

The key comes from the SARVAM_API_KEY environment variable (or the Windows user settings). It is never logged,
never written to disk, and scrubbed from any error text.
"""
import base64
import os
from pathlib import Path

import requests

import config
from .base import Engine, EngineError


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
    params: dict = {}          # extra form fields for /voices/clone; the variant below overrides these

    def available(self):
        return (True, "") if _key() else (False, "SARVAM_API_KEY is not set")

    def clone(self, ref_wav: Path, ref_text: str, text: str, out_wav: Path) -> dict:
        key = _key()
        if not key:
            raise EngineError("SARVAM_API_KEY is not set")
        try:
            with open(ref_wav, "rb") as fh:
                r = requests.post(
                    "https://api.sarvam.ai/voices/clone", headers={"api-subscription-key": key},
                    files={"ref_audio": ("ref.wav", fh, "audio/wav")},
                    data={"text": text, "language_code": "en-IN", "ref_text": ref_text, **self.params},
                    timeout=config.SARVAM_TIMEOUT_S)
        except requests.RequestException as exc:
            raise EngineError(f"Sarvam request failed ({type(exc).__name__})") from None
        if r.status_code != 200:
            raise EngineError(f"Sarvam HTTP {r.status_code}: {r.text[:200].replace(key, '<key>')}")
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        out_wav.write_bytes(base64.b64decode(r.json()["audio"]))
        return {"service": "sarvam", "params": dict(self.params)}


class SarvamVariant(Sarvam):
    """The same Sarvam cloning service with different settings (config.SARVAM_VARIANT_PARAMS), for a second, slightly different clone."""
    name = "sarvam2"
    params = config.SARVAM_VARIANT_PARAMS
