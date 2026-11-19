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


def word_error_rate(reference: str, heard: str) -> float:
    """Share of the reference's words that were not heard (case and punctuation ignored): 0.0 identical, 1.0 nothing matched."""
    norm = lambda s: re.sub(r"[^a-z0-9 ]", "", s.lower().replace("’", "'")).split()
    r, h = norm(reference), norm(heard)
    if not r:
        return 0.0
    d = [[i + j if i * j == 0 else 0 for j in range(len(h) + 1)] for i in range(len(r) + 1)]
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (r[i - 1] != h[j - 1]))
    return d[-1][-1] / len(r)


def pause_report(x: np.ndarray) -> dict:
    """Longest silence between speech, the amount of speech and the signal-to-noise ratio, from the Silero speech probabilities.

    snr_db compares the power of the speech frames with the quietest tenth of all frames (the room noise). On test recordings with
    noise added it followed the true value (true 30, 20, 15, 10, 3 dB gave 30, 21, 16, 12, 6 dB); echo, a quiet voice and a muffled
    voice did not lower it. It is None when there is too little speech to tell."""
    x = x.astype(np.float32)
    probs = spectra_prep.speech_probs(x)
    voiced = probs >= 0.5
    speech = np.flatnonzero(voiced)
    if len(speech) == 0:
        return {"speech_seconds": 0.0, "longest_pause": 0.0, "snr_db": None}
    gaps = np.diff(speech) - 1                                 # frames of silence between neighbouring speech frames
    n = len(probs)
    energy = np.array([np.mean(x[i * 512:(i + 1) * 512] ** 2) for i in range(n)]) + 1e-12
    snr = None
    if voiced.sum() >= 10:
        snr = round(float(10 * np.log10(energy[voiced].mean() / np.sort(energy)[: max(3, n // 10)].mean())), 1)
    return {"speech_seconds": round(len(speech) * _FRAME_S, 2), "longest_pause": round(float(gaps.max() if len(gaps) else 0) * _FRAME_S, 2), "snr_db": snr}


def review(x: np.ndarray) -> dict:
    """{"transcript": str|None, "issues": [sentences], "longest_pause": s, "speech_seconds": s, "fillers": [...], "stt_error": str|None}"""
    issues, transcript, stt_error, fillers = [], None, None, []
    pauses = {"speech_seconds": 0.0, "longest_pause": 0.0, "snr_db": None}
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
        if config.REQUIRE_SENTENCE_MATCH and len(transcript.split()) >= config.MIN_WORDS:
            miss = word_error_rate(config.SENTENCE, transcript)
            if miss > config.SENTENCE_MAX_WORD_ERROR:
                issues.append(f"We heard “{transcript[:80]}”, which is not the sentence on the screen. Please read the sentence again, slowly and clearly.")
    if pauses["snr_db"] is not None and pauses["snr_db"] < config.MIN_SNR_DB:
        issues.append("There is a lot of background noise. Please move somewhere quieter, hold the microphone a little closer, and try again.")
    if pauses["longest_pause"] > config.MAX_PAUSE_SECONDS:
        issues.append(f"There was a long pause in the middle ({pauses['longest_pause']:.1f} s). Please try again without stopping.")
    return {"transcript": transcript, "issues": issues, "stt_error": stt_error, "fillers": fillers, **pauses}
