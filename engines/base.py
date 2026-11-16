"""Interface every cloning engine implements."""
from pathlib import Path


class EngineError(RuntimeError):
    """A clone could not be made. The message is safe to log and to show to the operator."""


class Engine:
    name = "base"

    def available(self) -> tuple[bool, str]:
        """(ready, reason if not). Called before a run so a missing key or stopped worker is visible early."""
        return True, ""

    def clone(self, ref_wav: Path, ref_text: str, text: str, out_wav: Path) -> dict:
        """Say `text` in the voice of `ref_wav` (which says `ref_text`); write a WAV to `out_wav`.
        Return a dict of facts worth saving (for example {"sample_rate": 24000})."""
        raise NotImplementedError
