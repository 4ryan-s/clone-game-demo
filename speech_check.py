"""Judge how the participant spoke, so a bad take can be redone before clones are made.

Three checks on a recording (16 kHz mono):
  - words:   speech to text (stt.py) must find at least config.MIN_WORDS words;
  - fillers: "um", "uh", "hmm" and similar sounds in the transcript (Sarvam's verbatim mode keeps them);
  - pauses:  a silence in the middle of the speech longer than config.MAX_PAUSE_SECONDS, found with the Silero speech detector.
             (Sarvam's timestamps are one chunk for the whole clip, so they cannot show a pause; the detector can.)
Leading and trailing silence is ignored: only gaps between speech count.

Each problem becomes one plain sentence for the participant. If speech to text is unavailable the pause check still runs and
the transcript is None (the caller falls back to the fixed sentence)."""
import logging
import re

import numpy as np

import audio
import config
import spectra_prep
import stt

log = logging.getLogger("speech_check")
_FRAME_S = 512 / 16000
_FILLER = re.compile(r"^(u+m+|u+h+m*|e+r+m*|h+m+|m{2,})$")     # um umm uh uhh uhm er erm hmm mm mmm


def find_fillers(text: str) -> list[str]:
    """Filler sounds in a transcript, in order of appearance, without repeats."""
    found = []
    for tok in re.findall(r"[A-Za-z']+", text.lower()):
        if _FILLER.match(tok) and tok not in found:
            found.append(tok)
    return found


def pause_report(x: np.ndarray) -> dict:
    """Longest silence between speech and the amount of speech, from the Silero speech probabilities."""
    probs = spectra_prep.speech_probs(x.astype(np.float32))
    speech = np.flatnonzero(probs >= 0.5)
    if len(speech) == 0:
        return {"speech_seconds": 0.0, "longest_pause": 0.0}
    gaps = np.diff(speech) - 1                                 # frames of silence between neighbouring speech frames
    return {"speech_seconds": round(len(speech) * _FRAME_S, 2), "longest_pause": round(float(gaps.max() if len(gaps) else 0) * _FRAME_S, 2)}


def review(x: np.ndarray) -> dict:
    """{"transcript": str|None, "issues": [sentences], "longest_pause": s, "speech_seconds": s, "fillers": [...], "stt_error": str|None}"""
    issues, transcript, stt_error, fillers = [], None, None, []
    pauses = {"speech_seconds": 0.0, "longest_pause": 0.0}
    try:
        pauses = pause_report(x)
    except Exception as exc:  # noqa: BLE001   (the speech detector is a nice-to-have: never block a recording because it failed)
        log.warning("pause check failed: %s", exc)
    if config.STT_ENABLED:
        try:
            transcript = stt.transcribe(audio.to_wav_bytes(x))["text"]
        except stt.SttError as exc:
            stt_error = str(exc)
            log.warning("%s", stt_error)
    if stt_error and config.STT_REQUIRED:
        issues.append("We could not process your recording just now. Please try again in a moment.")
    if transcript is not None:
        if len(transcript.split()) < config.MIN_WORDS:
            issues.append("We could not make out any words. Please speak a little louder and clearer, and read the sentence again.")
        fillers = find_fillers(transcript)
        if fillers:
            issues.append(f"We heard hesitation sounds (“{fillers[0]}”). Please try again and say it in one go.")
    if pauses["longest_pause"] > config.MAX_PAUSE_SECONDS:
        issues.append(f"There was a long pause in the middle ({pauses['longest_pause']:.1f} s). Please try again without stopping.")
    return {"transcript": transcript, "issues": issues, "stt_error": stt_error, "fillers": fillers, **pauses}
