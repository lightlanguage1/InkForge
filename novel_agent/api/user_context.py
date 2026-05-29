"""Per-request user context via ContextVars.

Each HTTP request carries an X-API-Key header. The middleware hashes it
to derive a stable user_id that scopes all storage paths for that user.
"""
import hashlib
from contextvars import ContextVar

# Raw API key for the current request (used when calling the LLM)
_user_api_key: ContextVar[str] = ContextVar("user_api_key", default="")

# Stable 12-char hex id derived from the key (used for directory scoping)
_user_id: ContextVar[str] = ContextVar("user_id", default="default")


def get_user_api_key() -> str:
    return _user_api_key.get()


def get_user_id() -> str:
    return _user_id.get()


def derive_user_id(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()[:12]
