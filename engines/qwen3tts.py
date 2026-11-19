"""Qwen3-TTS (0.6B, open weights) on this machine, through the always-on worker in workers/qwen3tts_server.py."""
import threading
from pathlib import Path

import requests

import config
from .base import Engine, EngineError


_LOCK = threading.Lock()
_IN_FLIGHT = {url: 0 for url in config.QWEN_URLS}


def _by_load():
    """Worker URLs, least busy first (ties keep the configured order)."""
    with _LOCK:
        return sorted(config.QWEN_URLS, key=lambda u: _IN_FLIGHT[u])


class Qwen3TTS(Engine):
    name = "qwen3tts"

    def available(self):
        loading = False
        for url in config.QWEN_URLS:
            try:
                r = requests.get(url + "/health", timeout=2)
                if r.ok and r.json().get("ready"):
                    return True, ""
                loading = True
            except requests.RequestException:
                pass
        return False, "Qwen3-TTS worker is still loading" if loading else "Qwen3-TTS worker is not running (start workers/qwen3tts_server.py)"

    def clone(self, ref_wav: Path, ref_text: str, text: str, out_wav: Path) -> dict:
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        payload = {"ref": ref_wav.resolve().as_posix(), "ref_text": ref_text, "text": text, "out": out_wav.resolve().as_posix()}
        last = "no worker configured"
        for url in _by_load():                  # a worker that is down or still loading is skipped; the next one takes the job
            with _LOCK:
                _IN_FLIGHT[url] += 1
            try:
                r = requests.post(url + "/clone", timeout=config.QWEN_TIMEOUT_S, json=payload)
            except requests.RequestException as exc:
                last = f"Qwen3-TTS worker unreachable ({type(exc).__name__})"
                continue
            finally:
                with _LOCK:
                    _IN_FLIGHT[url] -= 1
            if r.status_code == 503:
                last = f"Qwen3-TTS worker not ready: {r.text[:100]}"
                continue
            if r.status_code != 200 or not r.json().get("ok"):
                raise EngineError(f"Qwen3-TTS failed: {r.text[:200]}")
            break
        else:
            raise EngineError(last)
        return {"service": config.QWEN_MODEL, "sample_rate": r.json().get("sample_rate")}
