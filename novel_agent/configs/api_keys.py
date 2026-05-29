"""Unified API key resolution.

Resolution order (first wins):
    1. Provider-specific environment variable (e.g. DEEPSEEK_API_KEY)
    2. INKFORGE_API_KEY (single key for all providers)
    3. ``.env`` file in the InkForge package root
    4. Error with clear message

.env format (one per line)::

    DEEPSEEK_API_KEY=sk-xxx
    # comments start with #

Usage:
    from novel_agent.configs.api_keys import resolve_api_key
    key = resolve_api_key("deepseek")
"""

import os
from pathlib import Path
from typing import Dict, Optional

_PROVIDER_ENV_MAP: Dict[str, str] = {
    "openai":    "OPENAI_API_KEY",
    "deepseek":  "DEEPSEEK_API_KEY",
    "claude":    "CLAUDE_API_KEY",
    "anthropic": "CLAUDE_API_KEY",
    "gemini":    "GEMINI_API_KEY",
}

_UNIFIED_KEY = "INKFORGE_API_KEY"

# Cached .env contents (loaded once)
_env_cache: Optional[Dict[str, str]] = None


def _load_dotenv() -> Dict[str, str]:
    """Parse .env from the package root. Returns {} if not found."""
    global _env_cache
    if _env_cache is not None:
        return _env_cache

    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    _env_cache = {}
    if not env_path.exists():
        return _env_cache

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                _env_cache[key] = value
    return _env_cache


def resolve_api_key(provider: str) -> str:
    """Return the API key for *provider*."""
    provider = provider.lower().strip()

    # 1. Provider-specific env var
    specific_var = _PROVIDER_ENV_MAP.get(provider)
    if specific_var:
        key = os.environ.get(specific_var)
        if key:
            return key

    # 2. Unified env var
    key = os.environ.get(_UNIFIED_KEY)
    if key:
        return key

    # 3. .env file
    dotenv = _load_dotenv()
    if specific_var and specific_var in dotenv:
        return dotenv[specific_var]
    if _UNIFIED_KEY in dotenv:
        return dotenv[_UNIFIED_KEY]

    _raise_missing_key(provider)


def _raise_missing_key(provider: str) -> None:
    specific_var = _PROVIDER_ENV_MAP.get(provider)
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if specific_var:
        msg = (
            f"API key not found for provider '{provider}'.\n"
            f"  Set the environment variable '{specific_var}',\n"
            f"  or set 'INKFORGE_API_KEY' for all providers,\n"
            f"  or create {env_path} with:\n"
            f"    {specific_var}=sk-xxx"
        )
    else:
        supported = ", ".join(_PROVIDER_ENV_MAP)
        msg = (
            f"Unknown provider '{provider}'. Supported: {supported}.\n"
            f"  Set 'INKFORGE_API_KEY' to cover any provider."
        )
    raise RuntimeError(msg)
