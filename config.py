"""Settings for the clone-spotting demo. Everything that is likely to change on demo day lives here."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SESSIONS_DIR = ROOT / "data" / "sessions"

# The fixed sentence every participant reads, and every clone speaks.
# PLACEHOLDER: pick the final one with the sentence test (10 to 15 words, reads in about 5 s).
SENTENCE = "Tell me about my last five transactions and the current interest rate."

# Recording limits (seconds). Sarvam accepts a reference of at most 15 s.
MIN_SECONDS = 3.5
MAX_SECONDS = 14.0
MIN_RMS_DBFS = -45.0       # quieter than this is rejected as "too quiet"
MAX_CLIPPED_FRACTION = 0.01

# Cloning engines, in slot order. A new engine is one file in engines/ plus its name here.
# Cards shown to the user = 1 real + one per engine, so 3 cards now; the game supports up to 4 (3 engines).
ENGINES = ["sarvam", "cosyvoice"]
MAX_ENGINES = 3

# Names shown on the reveal screen, after the participant has picked.
ENGINE_LABELS = {"sarvam": "Sarvam", "cosyvoice": "CosyVoice 2"}

# The clone check (see scoring.py). Margin below CUTOFF = called a clone. The model is read from the banking backend folder, read-only.
SPECTRA_BACKEND = Path("C:/Users/aryan/josh_voice_banking/backend/voice-banking-backend-pad-spectra")
CUTOFF = 6.0

# Playback only: every card is trimmed to the same lead/tail silence and set to the same loudness, so level and silence give nothing away.
PLAY_TARGET_RMS_DBFS = -23.0
PLAY_PAD_SECONDS = 0.2

COSYVOICE_URL ="http://127.0.0.1:8765"
COSYVOICE_PYTHON = "D:/clone_detection_tests/.venvs/cosyvoice/Scripts/python.exe"
COSYVOICE_TIMEOUT_S = 120
SARVAM_TIMEOUT_S = 90

# Shown on the consent page as the person to contact to delete a recording. Leave empty to say "ask the demo host".
CONTACT = ""

CONSENT_VERSION = "draft-1"   # bump whenever the consent wording changes; stored with every session
