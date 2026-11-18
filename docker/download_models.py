"""Download the clone-check model and the Qwen3-TTS weights into /app/models.

Run once on the server, before the stack stays up:

    docker compose run --rm --no-deps qwen python docker/download_models.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import config  # noqa: E402
import setup  # noqa: E402

os.environ.setdefault("HF_HOME", str(config.HF_HOME))
config.HF_HOME.mkdir(parents=True, exist_ok=True)

setup.ARGS = type("Args", (), {"dry_run": False})()
setup.part_spectra()

from huggingface_hub import snapshot_download  # noqa: E402

print(f"\n== Qwen3-TTS weights ({config.QWEN_MODEL})", flush=True)
snapshot_download(config.QWEN_MODEL)
print("\nModels are in", config.MODELS_DIR)
