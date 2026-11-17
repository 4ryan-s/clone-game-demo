"""Engine registry. To add a cloning engine: write engines/<name>.py with an Engine subclass, import it here,
add it to REGISTRY, and add its name to config.ENGINES (at most config.MAX_ENGINES)."""
import config
from .base import Engine, EngineError  # noqa: F401
from .cosyvoice import CosyVoice
from .qwen3tts import Qwen3TTS
from .sarvam import Sarvam

REGISTRY: dict[str, type[Engine]] = {"sarvam": Sarvam, "cosyvoice": CosyVoice, "qwen3tts": Qwen3TTS}


def enabled() -> list[Engine]:
    names = config.ENGINES[: config.MAX_ENGINES]
    unknown = [n for n in names if n not in REGISTRY]
    if unknown:
        raise RuntimeError(f"config.ENGINES names an engine that does not exist: {unknown}")
    return [REGISTRY[n]() for n in names]
