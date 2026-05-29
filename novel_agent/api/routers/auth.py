"""Auth endpoints — activation and user info."""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...user.auth import activate, ActivationError
from ...user.db import Database
from ...user.context import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])
logger = logging.getLogger(__name__)

# Global database instance — created once on first request
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


@router.post("/activate", response_model=ActivateResponse)
def activate_user(req: ActivateRequest):
    """Activate with an invite code and choose a display name."""
    try:
        result = activate(_get_db(), req.invite_code, req.display_name)
        return ActivateResponse(**result)
    except ActivationError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
