"""StoryDaemon - Agentic Novel Generation System."""

import logging
import sys

__version__ = "0.1.0"


def _fix_console_encoding() -> None:
    if sys.platform != "win32":
        return
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")


def setup_logging(level: int = logging.INFO) -> None:
    _fix_console_encoding()
    from .utils.log_manager import setup_logging as _setup
    _setup(level=level)
