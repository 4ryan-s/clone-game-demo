"""Qwen3-TTS (0.6B, open weights) on this machine, through the always-on worker in workers/qwen3tts_server.py."""
from pathlib import Path

import requests

import config
from .base import Engine, EngineError


class Qwen3TTS(Engine):
    name = "qwen3tts"

    def available(self):
        try:
            r = requests.get(config.QWEN_URL + "/health", timeout=2)
            return (True, "") if r.ok and r.json().get("ready") else (False, "Qwen3-TTS worker is still loading")
        except requests.RequestException:
            return False, "Qwen3-TTS worker is not running (start workers/qwen3tts_server.py)"

    def clone(self, ref_wav: Path, ref_text: str, text: str, out_wav: Path) -> dict:
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        try:
            r = requests.post(config.QWEN_URL + "/clone", timeout=config.QWEN_TIMEOUT_S, json={
                "ref": ref_wav.resolve().as_posix(), "ref_text": ref_text, "text": text, "out": out_wav.resolve().as_posix()})
        except requests.RequestException as exc:
            raise EngineError(f"Qwen3-TTS worker unreachable ({type(exc).__name__})") from None
        if r.status_code != 200 or not r.json().get("ok"):
            raise EngineError(f"Qwen3-TTS failed: {r.text[:200]}")
        return {"service": config.QWEN_MODEL, "sample_rate": r.json().get("sample_rate")}
