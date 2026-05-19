"""StoryDaemon - Agentic Novel Generation System."""

import logging
import sys

__version__ = "0.1.0"


def _fix_console_encoding() -> None:
    """Ensure UTF-8 output on Windows consoles."""
    if sys.platform != "win32":
        return
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")


def setup_logging(level: int = logging.INFO) -> None:
    """Configure structured logging for StoryDaemon.

    Args:
        level: Logging level (default: logging.INFO)
    """
    _fix_console_encoding()
    root = logging.getLogger("novel_agent")
    if root.handlers:
        return  # Already configured
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    ))
    root.addHandler(handler)
    root.setLevel(level)
