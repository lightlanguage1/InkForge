"""管理员端点 — 用户管理 / 邀请码管理 / 统计。"""

import logging
import secrets
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..user.db import Database
from ..user.auth import hash_password
from ..api.deps import require_admin

router = APIRouter(prefix="/api/v1/admin", tags=["管理"])
logger = logging.getLogger(__name__)

_db: Database | None = None


def _get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


# ═══════════════════════════════════════════
# 用户管理
# ═══════════════════════════════════════════

@router.get("/users")
def list_users(_admin=require_admin):
    return {"users": _get_db().list_all_users()}


@router.patch("/users/{user_id}")
def toggle_user(user_id: str, disabled: bool = True, _admin=require_admin):
    _get_db().set_user_disabled(user_id, disabled)
    return {"ok": True, "user_id": user_id, "disabled": disabled}


@router.post("/users/{user_id}/reset-password")
def admin_reset_password(user_id: str, _admin=require_admin):
    """管理员重置用户密码，返回新随机密码。"""
    new_pw = secrets.token_hex(4)
    pw_hash, salt = hash_password(new_pw)
    _get_db().set_password(user_id, pw_hash, salt)
    user = _get_db().get_user(user_id)
    return {"user_id": user_id, "display_name": user.get("display_name", ""), "new_password": new_pw}


# ═══════════════════════════════════════════
# 邀请码管理
# ═══════════════════════════════════════════

class GenerateCodesRequest(BaseModel):
    count: int = 5
    max_uses: int = 1
    days: int = 30


class UpdateExpiryRequest(BaseModel):
    days: int  # 0 = 永不过期


@router.get("/codes")
def list_codes(_admin=require_admin):
    return {"codes": _get_db().list_codes()}


@router.post("/codes")
def generate_codes(req: GenerateCodesRequest, _admin=require_admin):
    codes = _get_db().generate_codes(count=req.count, max_uses=req.max_uses, days=req.days)
    logger.info("管理员生成了 %d 个邀请码", len(codes))
    return {"generated": codes}


@router.post("/codes/{code}/toggle-strict")
def toggle_strict(code: str, _admin=require_admin):
    """切换严格过期模式。"""
    new_val = _get_db().toggle_strict_expiry(code)
    label = "严格过期（已注册用户也拦截）" if new_val else "宽松过期（仅拦截新注册）"
    logger.info("管理员切换邀请码 %s strict_expiry: %s", code, label)
    return {"updated": code, "strict_expiry": new_val, "label": label}


@router.patch("/codes/{code}")
def update_code_expiry(code: str, req: UpdateExpiryRequest, _admin=require_admin):
    """更新邀请码过期时间。days: 0=永不过期, N=N天后过期。"""
    _get_db().update_code_expiry(code, req.days)
    label = "永不过期" if req.days == 0 else f"{req.days} 天后"
    logger.info("管理员更新邀请码 %s 过期时间: %s", code, label)
    return {"updated": code, "days": req.days, "label": label}


@router.delete("/codes/{code}")
def delete_code(code: str, _admin=require_admin):
    _get_db().revoke_code(code)
    return {"revoked": code}


# ═══════════════════════════════════════════
# 日志
# ═══════════════════════════════════════════

@router.get("/logs")
def get_logs(service: str = "backend", lines: int = 100, _admin=require_admin):
    """获取日志（仅管理员）。service: backend | frontend"""
    if service not in ("backend", "frontend"):
        raise HTTPException(status_code=400, detail="service 仅支持 backend 或 frontend")
    if service == "backend":
        log_path = Path("/app/logs/inkforge.log")
    else:
        for p in ["/var/log/nginx/error.log", "/var/log/nginx/access.log"]:
            if Path(p).exists():
                log_path = Path(p)
                break
        else:
            return {"service": service, "logs": "nginx 日志文件未找到"}
    if not log_path.exists():
        return {"service": service, "logs": f"日志文件不存在: {log_path}"}
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
        tail = "\n".join(text.strip().split("\n")[-lines:])
        return {"service": service, "lines": lines, "logs": tail}
    except Exception as e:
        return {"service": service, "error": str(e), "logs": ""}


# ═══════════════════════════════════════════
# 统计
# ═══════════════════════════════════════════

@router.get("/stats")
def get_stats(_admin=require_admin):
    return _get_db().get_stats()
