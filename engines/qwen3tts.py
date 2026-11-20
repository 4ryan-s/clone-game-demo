"""Qwen3-TTS (0.6B, open weights) on this machine, through the always-on worker in workers/qwen3tts_server.py."""
import base64
import logging
import threading
import time
from pathlib import Path

import requests

import config
from .base import Engine, EngineError


log = logging.getLogger("qwen.client")
_LOCK = threading.Lock()
_IN_FLIGHT = {url: 0 for url in config.QWEN_URLS}
_DOWN_UNTIL = {url: 0.0 for url in config.QWEN_URLS}
DOWN_FOR_S = 20.0          # after a worker fails to answer, send new requests to the others for this long


def _by_load():
    """Worker URLs: ones not recently down first, then least busy (ties keep the configured order)."""
    now = time.time()
    with _LOCK:
        return sorted(config.QWEN_URLS, key=lambda u: (_DOWN_UNTIL[u] > now, _IN_FLIGHT[u]))


def _mark_down(url):
    with _LOCK:
        _DOWN_UNTIL[url] = time.time() + DOWN_FOR_S


class Qwen3TTS(Engine):
    name = "qwen3tts"
    serialize = False        # the workers batch simultaneous requests; locking here would force them to run one at a time

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
        # The audio goes in the request and comes back in the reply, so a worker can run on any machine (no shared disk needed).
        tag = out_wav.parent.parent.name              # sessions/<session id>/raw/<engine>.wav: the session id ties client and worker log lines together
        payload = {"ref_b64": base64.b64encode(Path(ref_wav).read_bytes()).decode(), "ref_text": ref_text, "text": text,
                   "language": config.QWEN_LANGUAGE, "tag": tag}
        headers = {"X-Qwen-Token": config.QWEN_TOKEN} if config.QWEN_TOKEN else {}
        last = "no worker configured"
        t0 = time.time()
        for url in _by_load():                  # a worker that is down or still loading is skipped; the next one takes the job
            with _LOCK:
                _IN_FLIGHT[url] += 1
                load = dict(_IN_FLIGHT)
            log.info("[%s] sending to %s (requests in flight per worker, including this one: %s)", tag, url, load)
            try:
                r = requests.post(url + "/clone", timeout=(5, config.QWEN_TIMEOUT_S), json=payload, headers=headers)
            except requests.ConnectionError as exc:          # includes ConnectTimeout: nothing is listening, or the machine is down
                last = f"Qwen3-TTS worker unreachable ({type(exc).__name__})"
                log.warning("[%s] %s unreachable (%s): trying the next worker; skipping it for %.0fs", tag, url, type(exc).__name__, DOWN_FOR_S)
                _mark_down(url)
                continue
            except requests.Timeout:
                # The worker took the job but did not answer in time. It is busy, not down: do NOT send the same clip to another worker
                # (that would double the GPU work) and do not steer other users away from it.
                log.error("[%s] %s did not answer within %ss: giving up on this clip", tag, url, config.QWEN_TIMEOUT_S)
                raise EngineError(f"Qwen3-TTS worker did not answer within {config.QWEN_TIMEOUT_S}s") from None
            except requests.RequestException as exc:
                last = f"Qwen3-TTS worker unreachable ({type(exc).__name__})"
                log.warning("[%s] %s request failed (%s): trying the next worker", tag, url, type(exc).__name__)
                continue
            finally:
                with _LOCK:
                    _IN_FLIGHT[url] -= 1
            if r.status_code == 503:
                last = f"Qwen3-TTS worker not ready: {r.text[:100]}"
                log.warning("[%s] %s not ready: trying the next worker", tag, url)
                _mark_down(url)
                continue
            if r.status_code == 401:
                raise EngineError("Qwen3-TTS worker refused the request: QWEN_TOKEN differs between the api and the worker")
            if r.status_code != 200 or not r.json().get("ok"):
                log.error("[%s] %s failed after %.1fs: HTTP %s %s", tag, url, time.time() - t0, r.status_code, r.text[:200])
                raise EngineError(f"Qwen3-TTS failed: {r.text[:200]}")
            body = r.json()
            if not body.get("audio_b64"):
                raise EngineError("Qwen3-TTS worker sent no audio (is it an old version? update the worker too)")
            out_wav.write_bytes(base64.b64decode(body["audio_b64"]))
            log.info("[%s] done by %s [%s] in %.1fs total: batch #%s of %s clip(s), waited %ss for the batch, generation %ss%s%s",
                     tag, url, body.get("worker"), time.time() - t0, body.get("batch_id"), body.get("batch_size"), body.get("queue_wait_s"),
                     body.get("seconds"), ", regenerated once (clip ran on)" if body.get("retried") else "",
                     f", tail of {body['tail_trimmed_s']}s cut" if body.get("tail_trimmed_s", 0) >= 1 else "")
            break
        else:
            raise EngineError(last)
        return {"service": config.QWEN_MODEL, "sample_rate": body.get("sample_rate"), "worker": body.get("worker"), "batch_size": body.get("batch_size"),
                "queue_wait_s": body.get("queue_wait_s"), "generation_s": body.get("seconds")}
