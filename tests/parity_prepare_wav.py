"""Checks that spectra_prep.prepare_wav gives the same samples as the banking backend's own prepare_wav.
Needs the backend folder (read only) and its packages, so it is a developer check, not part of setup.
    python tests/parity_prepare_wav.py <backend folder> <wav> [<wav> ...]"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, sys.argv[1])
import spectra_prep  # noqa: E402
from voiceprint.utils.pad_scorer import prepare_wav as backend_prepare  # noqa: E402

worst = 0.0
for f in sys.argv[2:]:
    x, sr = sf.read(f, dtype="float32")
    x = x if x.ndim == 1 else x.mean(axis=1)
    assert sr == 16000, f"{f} is {sr} Hz; use 16 kHz clips"
    a, b = spectra_prep.prepare_wav(x), backend_prepare(x, 16000, use_preemphasis=True)
    d = float(np.max(np.abs(a - b)))
    worst = max(worst, d)
    print(f"{len(x) / 16000:6.1f} s  max abs difference {d:.2e}  {Path(f).name}")
print("PASS" if worst < 1e-6 else "FAIL", f"(worst {worst:.2e})")
sys.exit(0 if worst < 1e-6 else 1)
