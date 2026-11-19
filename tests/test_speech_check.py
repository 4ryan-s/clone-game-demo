"""Checks for speech_check.py.   python tests/test_speech_check.py [speech.wav]
The filler checks need nothing. The pause checks need a 16 kHz mono recording of someone speaking (any, 3 s or more) as the
argument; the speech detector cannot be tested with synthetic tones."""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import speech_check  # noqa: E402


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        sys.exit(1)


ff = speech_check.find_fillers
check(ff("Show me um my last five transactions uh and the um interest rate.") == ["um", "uh"], "finds um and uh, once each")
check(ff("ummm, I want hmm to check erm my balance") == ["ummm", "hmm", "erm"], "finds stretched and other filler sounds")
check(ff("Please transfer the amount to my savings account.") == [], "no fillers in a clean sentence")
check(ff("The umbrella, the human, the hummingbird and the error") == [], "words that merely contain um, hm or er are not fillers")
check(ff("") == [], "empty text is fine")

# review() with a stand-in for speech to text (no network)
silent = np.zeros(4 * 16000, dtype=np.float32)
real_transcribe = speech_check.stt.transcribe


def fail(_wav):
    raise speech_check.stt.SttError("Sarvam speech-to-text failed: HTTP 429")


speech_check.stt.transcribe = fail
config.STT_REQUIRED = True
r = speech_check.review(silent)
check(r["transcript"] is None and any("try again" in i for i in r["issues"]), "speech to text down and required: the person is asked to try again (no wrong words slip through)")
config.STT_REQUIRED = False
r = speech_check.review(silent)
check(r["transcript"] is None and not r["issues"] and r["stt_error"], "speech to text down and not required: carries on with no transcript")
config.STT_REQUIRED = True
speech_check.stt.transcribe = lambda _w: {"text": "um show me my last five transactions", "seconds": 0.1, "language": "en-IN"}
r = speech_check.review(silent)
check(r["fillers"] == ["um"] and any("hesitation" in i for i in r["issues"]), "an 'um' in the words sends the recording back")
speech_check.stt.transcribe = lambda _w: {"text": "", "seconds": 0.1, "language": None}
r = speech_check.review(silent)
check(any("could not make out" in i for i in r["issues"]), "no words found sends the recording back")
speech_check.stt.transcribe = lambda _w: {"text": "show me my last five transactions", "seconds": 0.1, "language": "en-IN"}
r = speech_check.review(silent)
check(not r["issues"] and r["transcript"] == "show me my last five transactions", "clean words pass and are returned as the transcript")
speech_check.stt.transcribe = real_transcribe

if len(sys.argv) > 1:
    x, sr = sf.read(sys.argv[1], dtype="float32")
    x = x if x.ndim == 1 else x.mean(axis=1)
    assert sr == 16000, "use a 16 kHz clip"
    base = speech_check.pause_report(x)
    check(base["speech_seconds"] > 1.0, f"speech found in the clip ({base['speech_seconds']} s of speech)")
    mid = len(x) // 2
    gapped = np.concatenate([x[:mid], np.zeros(int(2.8 * 16000), dtype="float32"), x[mid:]])
    rep = speech_check.pause_report(gapped)
    check(rep["longest_pause"] >= 2.5, f"a 2.8 s silence inserted in the middle is found ({rep['longest_pause']} s)")
    check(rep["longest_pause"] > config.MAX_PAUSE_SECONDS > base["longest_pause"] - 0.0001 or base["longest_pause"] <= config.MAX_PAUSE_SECONDS,
          f"the inserted pause is over the limit ({config.MAX_PAUSE_SECONDS} s) and the original clip is not ({base['longest_pause']} s)")
    lead = np.concatenate([np.zeros(int(3 * 16000), dtype="float32"), x, np.zeros(int(3 * 16000), dtype="float32")])
    check(abs(speech_check.pause_report(lead)["longest_pause"] - base["longest_pause"]) < 0.1, "silence before and after the speech is ignored")
else:
    print("(pause checks skipped: pass a speech recording as an argument)")
print("ALL PASSED")
