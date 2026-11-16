"""CosyVoice 2 on this machine's GPU, through the small always-on worker in workers/cosyvoice_server.py.
The worker keeps the model loaded so a clone takes seconds instead of a model load."""
from pathlib import Path

import requests

import config
from .base import Engine, EngineError


class CosyVoice(Engine):
    name = "cosyvoice"

    def available(self):
        try:
            r = requests.get(config.COSYVOICE_URL + "/health", timeout=2)
            return (True, "") if r.ok and r.json().get("ready") else (False, "CosyVoice worker is still loading")
        except requests.RequestException:
            return False, "CosyVoice worker is not running (start workers/cosyvoice_server.py)"

    def clone(self, ref_wav: Path, ref_text: str, text: str, out_wav: Path) -> dict:
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        try:
            r = requests.post(config.COSYVOICE_URL + "/clone", timeout=config.COSYVOICE_TIMEOUT_S, json={
                "ref": ref_wav.resolve().as_posix(), "ref_text": ref_text, "text": text, "out": out_wav.resolve().as_posix()})
        except requests.RequestException as exc:
            raise EngineError(f"CosyVoice worker unreachable ({type(exc).__name__})") from None
        if r.status_code != 200 or not r.json().get("ok"):
            raise EngineError(f"CosyVoice failed: {r.text[:200]}")
        return {"service": "cosyvoice2-0.5b", "sample_rate": r.json().get("sample_rate")}
