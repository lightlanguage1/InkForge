"""Auth endpoints — activation and user info."""
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ...user.auth import activate, ActivationError, register, login, reset_password, AuthError
from ...user.db import Database
from ...user.context import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])
logger = logging.getLogger(__name__)

_db: Database | None = None


def _get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


class ActivateRequest(BaseModel):
    invite_code: str
    display_name: str


class ActivateResponse(BaseModel):
    token: str
    user_id: str
    display_name: str


class RegisterRequest(BaseModel):
    invite_code: str
    display_name: str
    password: str


class LoginRequest(BaseModel):
    display_name: str
    password: str


class UpdateMeRequest(BaseModel):
    display_name: str
    password: str


class ResetRequest(BaseModel):
    display_name: str
    invite_code: str
    new_password: str


@router.post("/activate", response_model=ActivateResponse)
def activate_user(req: ActivateRequest, request: Request):
    """[兼容旧版] 邀请码激活。"""
    ip = request.client.host if request.client else ""
    try:
        result = activate(_get_db(), req.invite_code, req.display_name, ip=ip)
        return ActivateResponse(**result)
    except ActivationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/register", response_model=ActivateResponse)
def register_user(req: RegisterRequest, request: Request):
    """新用户注册——邀请码 + 用户名 + 密码。"""
    ip = request.client.host if request.client else ""
    try:
        result = register(_get_db(), req.invite_code, req.display_name, req.password, ip=ip)
        return ActivateResponse(**result)
    except AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=ActivateResponse)
def login_user(req: LoginRequest, request: Request):
    """用户名 + 密码登录。"""
    ip = request.client.host if request.client else ""
    try:
        result = login(_get_db(), req.display_name, req.password, ip=ip)
        return ActivateResponse(**result)
    except AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reset-password")
def reset_user_password(req: ResetRequest):
    """重置密码——用户名 + 邀请码验证。"""
    try:
        reset_password(_get_db(), req.display_name, req.invite_code, req.new_password)
        return {"ok": True}
    except AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/me")
def update_me(req: UpdateMeRequest):
    """修改当前用户的显示名称（需验证密码）。"""
    user_id = get_current_user()
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    name = req.display_name.strip()
    if not name or len(name) > 30:
        raise HTTPException(status_code=400, detail="用户名需在1-30个字符之间")
    from ...user.auth import verify_password
    db = _get_db()
    user = db.get_user(user_id)
    if not user or not user.get("password_hash"):
        raise HTTPException(status_code=403, detail="账户未设置密码，请先重置密码")
    if not verify_password(req.password, user["salt"], user["password_hash"]):
        raise HTTPException(status_code=403, detail="密码错误")
    existing = db.get_user_by_name(name)
    if existing and existing["user_id"] != user_id:
        raise HTTPException(status_code=409, detail="用户名已被使用")
    db.update_display_name(user_id, name)
    return {"ok": True, "display_name": name}


@router.get("/me")
def whoami():
    """Return current user info (requires valid token)."""
    user_id = get_current_user()
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    user = _get_db().get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user
