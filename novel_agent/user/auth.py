"""Activation & JWT logic — pure stdlib, no third-party JWT library."""
import hashlib
import hmac
import json
import time
from base64 import urlsafe_b64encode, urlsafe_b64decode
from typing import Optional

from .db import Database

_SECRET = "INKFORGE_INTERNAL_SIGNING_KEY_2026_v1"  # keep this stable across restarts

# ── JWT helpers ───────────────────────────────────────────────────────────────

def _b64(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode()


def _deb64(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return urlsafe_b64decode(s)


def create_token(user_id: str, expire_days: int = 30) -> str:
    """Create a self-signed JWT-like token."""
    header = _b64(b'{"alg":"HS256","typ":"JWT"}')
    now = int(time.time())
    payload = _b64(json.dumps({
        "sub": user_id,
        "iat": now,
        "exp": now + expire_days * 86400,
    }).encode())
    sig = hmac.new(
        _SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256
    ).digest()
    return f"{header}.{payload}.{_b64(sig)}"


def verify_token(token: str) -> Optional[str]:
    """Verify token and return user_id, or None."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, payload, sig = parts

        expected = hmac.new(
            _SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(_deb64(sig), expected):
            return None

        data = json.loads(_deb64(payload))
        if data.get("exp", 0) < int(time.time()):
            return None

        return data["sub"]
    except Exception:
        return None


# ── Activation ────────────────────────────────────────────────────────────────

class ActivationError(Exception):
    pass


def activate(db: Database, invite_code: str, display_name: str, ip: str = "") -> dict:
    """Validate invite code, create or re-login user, return {token, user_id, display_name}."""
    display_name = display_name.strip()
    if not display_name or len(display_name) > 30:
        raise ActivationError("用户名需在1-30个字符之间")
    if not invite_code.strip():
        raise ActivationError("请输入邀请码")

    # Re-login: if this invite code already has a user, return that user
    existing = db.get_user_by_invite_code(invite_code)
    if existing:
        db.touch_user(existing["user_id"], ip=ip)
        token = create_token(existing["user_id"])
        return {"token": token, "user_id": existing["user_id"], "display_name": existing["display_name"]}

    err = db.validate_code(invite_code)
    if err:
        raise ActivationError(err)

    if not db.consume_code(invite_code):
        raise ActivationError("邀请码已达使用上限")

    user_id = db.get_or_create_user(invite_code, display_name, ip=ip)
    token = create_token(user_id)

    return {
        "token": token,
        "user_id": user_id,
        "display_name": display_name,
    }
