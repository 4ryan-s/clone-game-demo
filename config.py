"""Settings for the clone-spotting demo. Everything that is likely to change on demo day lives here.

Paths are relative to this folder, so a fresh clone works after `python setup.py`. To point at models or environments that
already exist on one machine, create `local_config.py` next to this file (git ignores it) and assign any name from this file.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_env():
    """Read project .env into the process. A variable already set in the shell wins."""
    path = ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and name not in os.environ:
            os.environ[name] = value


_load_env()

SESSIONS_DIR = ROOT / "data" / "sessions"                # working data of one play-through; deleted when it ends
VOICE_SAMPLES_DIR = ROOT / "data" / "voice_samples"      # numbered recordings kept with consent (see voicebank.py); data/ is git-ignored
MODELS_DIR = ROOT / "models"       # downloaded by setup.py (not in git: several GB)
VENVS_DIR = ROOT / ".venvs"        # one Python environment per local engine, created by setup.py


def venv_python(name: str) -> str:
    return str(VENVS_DIR / name / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python"))


# The fixed sentence every participant reads, and every clone speaks.
# PLACEHOLDER: pick the final one with the sentence test (10 to 15 words, reads in about 5 s).
SENTENCE = "Hello everyone! I’m here in Hyderabad, India, attending the Ruby Conference today. Looking forward to an amazing experience!"

# Recording limits (seconds). Sarvam accepts a reference of at most 15 s.
MIN_SECONDS = 3.5
MAX_SECONDS = 14.0
MIN_RMS_DBFS = -45.0       # quieter than this is rejected as "too quiet"
MAX_CLIPPED_FRACTION = 0.01

# Cloning engines, in slot order. A new engine is one file in engines/ plus its name here.
# Cards shown to the user = 1 real + one per engine, so three engines give four cards.
ENGINES = ["sarvam", "sarvam2", "qwen3tts"]
MAX_ENGINES = 3

# Settings for the second Sarvam clone ("sarvam2"). Form fields of POST /voices/clone, sent as text.
SARVAM_VARIANT_PARAMS = {"remove_background_noise": "true", "enable_qc": "true", "pace": "0.95"}

# Names shown on the reveal screen, after the participant has picked.
ENGINE_LABELS = {"sarvam": "Sarvam", "sarvam2": "Sarvam (other settings)", "qwen3tts": "Qwen3-TTS"}

# The clone check (see scoring.py). Margin below CUTOFF = called a clone.
CUTOFF = 6.0
SPECTRA_ONNX = Path(os.environ.get("SPECTRA_ONNX", MODELS_DIR / "spectra_aasist3.onnx"))

# Playback only: every card is trimmed to the same lead/tail silence and set to the same loudness, so level and silence give nothing away.
PLAY_TARGET_RMS_DBFS = -23.0
PLAY_PAD_SECONDS = 0.2

# Local engines. Each runs as a small always-on worker in its own environment and keeps its model loaded on the GPU.
QWEN_URL = os.environ.get("QWEN_URL", "http://127.0.0.1:8766")
QWEN_PYTHON = venv_python("qwen")
QWEN_MODEL = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"        # Hugging Face id, downloaded into MODELS_DIR/hf by setup.py
QWEN_TIMEOUT_S = 120

HF_HOME = MODELS_DIR / "hf"
SARVAM_TIMEOUT_S = 90
SARVAM_MAX_RETRIES = 1        # on HTTP 429 (rate limit): retry a clone at most once, so a throttle does not trigger a burst of extra calls
SARVAM_RETRY_BASE_S = 4.0     # wait before the single retry (unless the server sends a longer Retry-After header)

# Shown on the consent page as the person to contact to delete a recording. Leave empty to say "ask the demo host".
CONTACT = ""

CONSENT_VERSION = "draft-2"   # bump whenever the consent wording changes; stored with every session

try:                           # machine-specific overrides (paths to models and environments that already exist here)
    from local_config import *  # noqa: F401,F403
except ImportError:
    pass
