"""Live check (calls Sarvam, needs SARVAM_API_KEY): do the Sarvam clones match the speed of the original?
    python tests/sarvam_pace_live.py <reference.wav> "<exactly what the reference says>"
Prints the original's speech length, the clone's first try, the pace Sarvam was asked for, and the final length."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import audio  # noqa: E402
import spectra_prep  # noqa: E402
from engines.sarvam import Sarvam, SarvamVariant  # noqa: E402

ref, words = Path(sys.argv[1]), sys.argv[2]
x, sr = audio.read_wav_bytes(ref.read_bytes())
target = spectra_prep.speech_span(audio.to_16k(x, sr))
print(f"original speech length {target:.1f} s")
out = Path(tempfile.mkdtemp(prefix="sarvam_pace_"))
worst = 0.0
for cls in (Sarvam, SarvamVariant):
    e = cls()
    info = e.clone(ref, words, words, out / f"{e.name}.wav")
    y, ysr = audio.read_wav_bytes((out / f"{e.name}.wav").read_bytes())
    span = spectra_prep.speech_span(audio.to_16k(y, ysr))
    worst = max(worst, abs(span / target - 1))
    print(f"{e.name:8s} first try {info.get('first_s')} s, pace used {info['pace']}, final {span:.1f} s ({100 * (span / target - 1):+.0f}% against the original) {info.get('pace_match_error', '')}")
print("PASS" if worst <= 0.12 else "FAIL", f"(worst difference {100 * worst:.0f}%, allowed 12%)")
sys.exit(0 if worst <= 0.12 else 1)
