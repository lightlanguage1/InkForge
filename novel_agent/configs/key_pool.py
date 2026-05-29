"""Round-robin API key pool — rotates across multiple DeepSeek keys."""
import os
import threading
import itertools

_ENV_KEY = "INKFORGE_API_KEYS"

_keys: list[str] = []
_cycle: itertools.cycle | None = None
_lock = threading.Lock()


def _load():
    global _keys, _cycle
    raw = os.getenv(_ENV_KEY, "")
    _keys = [k.strip() for k in raw.split(",") if k.strip().startswith("sk-")]
    if not _keys:
        # fall back to single key
        single = os.getenv("DEEPSEEK_API_KEY") or os.getenv("STORYDAEMON_API_KEY") or ""
        if single.strip():
            _keys = [single.strip()]
    _cycle = itertools.cycle(_keys) if _keys else None


def get_key() -> str:
    """Return the next API key (round-robin). Thread-safe."""
    global _cycle
    if _cycle is None:
        with _lock:
            if _cycle is None:
                _load()
    with _lock:
        return next(_cycle) if _cycle else ""


def key_count() -> int:
    global _cycle
    if _cycle is None:
        _load()
    return len(_keys)
