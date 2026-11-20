"""Logging for the api process: one format, a LOG_LEVEL setting, and an access log without the noise.

LOG_LEVEL=DEBUG shows more (per-engine details); the default is INFO.
What is logged is meant for finding problems: ids, timings, sizes, which worker did the job, error text.
It never contains what a participant said (the transcript) or their audio."""
import logging
import os

FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"

# Requests that are made over and over by the page or by the health checks. Not logged unless they fail.
_NOISY = ("/status", "/api/health", "/api/config", "/api/stats", "/assets/", "/favicon", "/josh-logo", "/recorder-worklet")


class QuietAccessLog(logging.Filter):
    """Drops the repetitive access lines (status polling every 0.5 s, health checks, page assets). Errors (HTTP 400 and up) are always kept."""

    def filter(self, record):
        args = record.args
        if isinstance(args, tuple) and len(args) >= 5:
            try:
                if int(args[4]) >= 400:
                    return True
            except (TypeError, ValueError):
                pass
        msg = record.getMessage()
        return not any(p in msg for p in _NOISY)


def setup() -> None:
    level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    logging.basicConfig(level=level, format=FORMAT)
    logging.getLogger("uvicorn.access").addFilter(QuietAccessLog())
    logging.getLogger("urllib3").setLevel(logging.WARNING)
