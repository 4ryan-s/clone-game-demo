"""Speech to text with Sarvam (POST /speech-to-text). Used on the participant's recording to get the words they said.

Those words are then (1) the text every clone speaks and (2) the exact transcript of the reference audio, which Qwen3-TTS
needs: with a transcript that does not match the audio it produced unintelligible speech in our test, with the right one it
was clean. `verbatim` mode keeps filler words ("um", "uh") as spoken, so the transcript matches the audio and the fillers can be flagged.

The key comes from SARVAM_API_KEY like the cloning engine and is never logged or returned in an error."""
import logging
import time

import requests

import config
from engines.sarvam import _key


log = logging.getLogger("stt")


class SttError(RuntimeError):
    """The recording could not be turned into text. The message is safe to log."""


def transcribe(wav_bytes: bytes) -> dict:
    """Return {"text": str, "seconds": float, "language": str|None}. Raises SttError."""
    key = _key()
    if not key:
        raise SttError("SARVAM_API_KEY is not set")
    t0 = time.time()
    last = "no attempt made"
    for attempt in range(3):                                  # retries (with a short wait) for a dropped connection, a busy service or a rate limit
        if attempt:
            time.sleep(attempt)
        try:
            r = requests.post(
                "https://api.sarvam.ai/speech-to-text", headers={"api-subscription-key": key},
                files={"file": ("recording.wav", wav_bytes, "audio/wav")},
                data={"model": config.STT_MODEL, "mode": config.STT_MODE, "language_code": config.STT_LANGUAGE},
                timeout=config.STT_TIMEOUT_S)
        except requests.RequestException as exc:
            last = f"request failed ({type(exc).__name__})"
            log.warning("speech to text attempt %d/3 failed: %s", attempt + 1, last)
            continue
        if r.status_code == 200:
            j = r.json()
            out = {"text": (j.get("transcript") or "").strip(), "seconds": round(time.time() - t0, 2), "language": j.get("language_code")}
            log.info("speech to text ok in %.1fs (%d words, language %s, attempt %d)", out["seconds"], len(out["text"].split()), out["language"], attempt + 1)
            return out
        last = f"HTTP {r.status_code}: {r.text[:150].replace(key, '<key>')}"
        log.warning("speech to text attempt %d/3 failed: %s", attempt + 1, last)
        if r.status_code < 500 and r.status_code != 429:
            break
    raise SttError(f"Sarvam speech-to-text failed: {last}")
