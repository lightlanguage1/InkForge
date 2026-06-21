"""公告 API — 公开查看 + 管理 CRUD。"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .db import AnnouncementDB
from ..user.context import get_current_user
from ..user.db import Database as UserDB

router = APIRouter(prefix="/api/v1/announcements", tags=["公告"])
logger = logging.getLogger(__name__)

_db: AnnouncementDB | None = None


def _ann_db() -> AnnouncementDB:
    global _db
    if _db is None:
        _db = AnnouncementDB()
    return _db


def _require_admin():
    """手动 admin 检查——不依赖 api/deps 避免循环引用。"""
    user_id = get_current_user()
    user = UserDB().get_user(user_id)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return True


# ═══════════════════════════════════════════
# 公开
# ═══════════════════════════════════════════

@router.get("/active")
def list_active(limit: int = 5):
    """获取当前有效公告列表，无需登录。"""
    try:
        return {"announcements": _ann_db().list_active(limit)}
    except Exception as e:
        logger.warning("获取公告失败: %s", e)
        return {"announcements": []}


# ═══════════════════════════════════════════
# 管理（需要 admin）
# ═══════════════════════════════════════════

class AnnouncementBody(BaseModel):
    title: str
    content: str = ""
    tag: str = "公告"


class AnnouncementUpdate(BaseModel):
    title: str = ""
    content: str = ""
    tag: str = ""
    active: int | None = None


@router.get("/all")
def list_all(_admin: str = ""):
    """管理端：所有公告列表。"""
    _require_admin()
    return {"announcements": _ann_db().list_all()}


@router.post("/")
def create(body: AnnouncementBody):
    """创建公告。"""
    _require_admin()
    ann_id = _ann_db().create(body.title, body.content, body.tag)
    logger.info("公告已创建: id=%d title=%s", ann_id, body.title)
    return {"ok": True, "id": ann_id}


@router.patch("/{ann_id}")
def update(ann_id: int, body: AnnouncementUpdate):
    """更新公告。"""
    _require_admin()
    _ann_db().update(ann_id, body.title, body.content, body.tag, body.active)
    return {"ok": True, "id": ann_id}


@router.delete("/{ann_id}")
def archive(ann_id: int):
    """归档公告（软删除）。"""
    _require_admin()
    _ann_db().delete(ann_id)
    return {"ok": True, "id": ann_id}
