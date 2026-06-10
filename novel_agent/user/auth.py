"""Auth logic — activation, registration, login, JWT — pure stdlib."""
import hashlib
import hmac
import json
import os
import secrets
import time
from base64 import urlsafe_b64encode, urlsafe_b64decode
from typing import Optional

from .db import Database

_SECRET = "INKFORGE_INTERNAL_SIGNING_KEY_2026_v1"  # keep this stable across restarts

# ── password hashing ──────────────────────────────────────────────────────────

def hash_password(password: str, salt: str = "") -> tuple[str, str]:
    """Hash a password with pbkdf2_hmac. Returns (hash_hex, salt_hex)."""
    if not salt:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return dk.hex(), salt


def verify_password(password: str, salt: str, stored_hash: str) -> bool:
    """Check password against stored hash."""
    dk, _ = hash_password(password, salt)
    return hmac.compare_digest(dk, stored_hash)

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


# ── Registration / Login ──────────────────────────────────────────────────────

class AuthError(Exception):
    pass


def register(db: Database, invite_code: str, display_name: str, password: str, ip: str = "") -> dict:
    """Register a new user with invite code + password. Returns {token, user_id, display_name}."""
    display_name = display_name.strip()
    if not display_name or len(display_name) > 30:
        raise AuthError("用户名需在1-30个字符之间")
    if not invite_code.strip():
        raise AuthError("请输入邀请码")
    if not password or len(password) < 4:
        raise AuthError("密码至少4个字符")

    # Check name uniqueness
    existing = db.get_user_by_name(display_name)
    if existing:
        raise AuthError("用户名已被使用")

    err = db.validate_code(invite_code)
    if err:
        raise AuthError(err)

    if not db.consume_code(invite_code):
        raise AuthError("邀请码已达使用上限")

    pw_hash, salt = hash_password(password)
    user_id = db.register_user(invite_code, display_name, pw_hash, salt, ip=ip)
    user = db.get_user(user_id)
    token = create_token(user_id)
    return {"token": token, "user_id": user_id, "display_name": display_name, "is_admin": user.get("is_admin", 0)}


def login(db: Database, display_name: str, password: str, ip: str = "") -> dict:
    """Login with display name + password. Returns {token, user_id, display_name}."""
    display_name = display_name.strip()
    if not display_name or not password:
        raise AuthError("请输入用户名和密码")

    user = db.get_user_by_name(display_name)
    if not user:
        raise AuthError("用户名不存在")

    if user.get("disabled"):
        raise AuthError("账户已被禁用，请联系管理员")

    # 严格过期：邀请码过期且 strict_expiry=1 → 已注册用户也无法登录
    if db.is_code_expired_for_user(user["user_id"]):
        raise AuthError("你的邀请码已过期，请联系管理员续期或关闭严格过期限制")

    if not user.get("password_hash"):
        raise AuthError("账户未设置密码，请联系管理员重置")

    if not verify_password(password, user["salt"], user["password_hash"]):
        raise AuthError("密码错误")

    db.touch_user(user["user_id"], ip=ip)
    token = create_token(user["user_id"])
    return {"token": token, "user_id": user["user_id"], "display_name": user["display_name"], "is_admin": user.get("is_admin", 0)}


def reset_password(db: Database, display_name: str, invite_code: str, new_password: str) -> None:
    """Reset password by verifying invite code ownership."""
    display_name = display_name.strip()
    if not new_password or len(new_password) < 4:
        raise AuthError("新密码至少4个字符")

    user = db.get_user_by_name(display_name)
    if not user:
        raise AuthError("用户名不存在")

    if user["invite_code"] != invite_code.strip().upper():
        raise AuthError("邀请码不匹配")

    pw_hash, salt = hash_password(new_password)
    db.set_password(user["user_id"], pw_hash, salt)
