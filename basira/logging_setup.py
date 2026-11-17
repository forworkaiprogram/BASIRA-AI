"""Application-wide logging and safe error types."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from .config import logs_dir

_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    d: Path = logs_dir()
    handler = logging.FileHandler(d / "basira.log", encoding="utf-8")
    console = logging.StreamHandler(sys.stderr)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(fmt)
    console.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
    root.addHandler(console)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger("basira." + name)


class BasiraError(Exception):
    """Base class for all BASIRA errors."""


class ModelNotAvailableError(BasiraError):
    """A required model file is missing; the feature must stay disabled."""


class HardwareUnavailableError(BasiraError):
    """A hardware device (camera/microphone/speaker) is not available."""


class EngineNotLoadedError(BasiraError):
    """An engine was used before it was loaded."""
