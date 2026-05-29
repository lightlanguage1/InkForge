"""Per-request user context via ContextVar — zero dependency, fast path."""
from contextvars import ContextVar

_user_id: ContextVar[str] = ContextVar("user_id", default="")


def set_current_user(user_id: str) -> None:
    _user_id.set(user_id)


def get_current_user() -> str:
    return _user_id.get()
