"""社区模块 — 作品发布 / 阅读 / 段落评论 / 聊天室。"""

import logging
import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..user.db import Database
from ..user.context import get_current_user
from ..api.routers.projects import _has_cover

router = APIRouter(prefix="/api/v1/community", tags=["社区"])
logger = logging.getLogger(__name__)

_db: Database | None = None


def _get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


def _get_user_name(user_id: str) -> str:
    u = _get_db().get_user(user_id)
    return u.get("display_name", "") if u else ""


# ═══════════════════════════════════════════
# 读取（社区阅读）
# ═══════════════════════════════════════════

@router.get("/read/{project_id}")
def read_project(project_id: str, tick: int = Query(None, description="指定幕号，不传返回全部")):
    """读取已发布作品的内容（全文或指定幕）。"""
    # 验证已发布
    if not _get_db().get_publish_status(project_id):
        raise HTTPException(status_code=404, detail="作品未发布或不存在")

    # 从文件系统找项目目录
    posts = _get_db().list_published_posts()
    user_id = ""
    for p in posts:
        if p["project_id"] == project_id:
            user_id = p["user_id"]
            break
    if not user_id:
        raise HTTPException(status_code=404, detail="作品未发布或不存在")

    base = Path("/app/work/users") / user_id / "novels"
    project_dir = None
    for d in base.iterdir():
        if d.is_dir() and d.name == project_id:
            project_dir = d
            break
    if not project_dir:
        raise HTTPException(status_code=404, detail="作品目录不存在")

    scene_dir = project_dir / "scenes"
    if not scene_dir.exists():
        return {"scenes": [], "title": ""}

    # 读 state.json
    state = {}
    state_path = project_dir / "state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))

    # 读所有场景（工作区只包含当前 HEAD 的场景，无需过滤）
    scene_files = sorted(scene_dir.glob("scene_*.md"))
    scenes = []
    for sf in scene_files:
        raw = sf.read_text(encoding="utf-8")
        # 解析标题和正文
        title = ""
        body = raw
        m = re.match(r"^#\s*(.+)$", raw, re.MULTILINE)
        if m:
            title = m.group(1).strip()
            body = raw[m.end():].strip()
        # 按段落分割（空行分隔）
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", body) if p.strip()]
        scenes.append({
            "file": sf.name,
            "tick": int(sf.stem.replace("scene_", "")) if sf.stem.startswith("scene_") else 0,
            "title": title,
            "paragraphs": paragraphs,
            "word_count": len(raw),
        })

    # 如果指定 tick，只返回该幕
    if tick is not None:
        scenes = [s for s in scenes if s["tick"] == tick]

    return {
        "title": state.get("novel_name", ""),
        "scenes": scenes,
    }


# ═══════════════════════════════════════════
# 发布开关
# ═══════════════════════════════════════════

class PublishToggle(BaseModel):
    published: bool


@router.patch("/publish/{project_id}")
def toggle_publish(project_id: str, body: PublishToggle):
    user_id = get_current_user()
    return {"published": _get_db().set_publish(project_id, user_id, body.published)}


@router.get("/publish/{project_id}")
def get_publish_status(project_id: str):
    return {"published": _get_db().get_publish_status(project_id)}


# ═══════════════════════════════════════════
# 社区首页
# ═══════════════════════════════════════════

@router.get("/posts")
def list_posts():
    """社区首页 — 已发布作品列表。"""
    posts = _get_db().list_published_posts()
    result = []
    for p in posts:
        pid = p["project_id"]
        base = Path("/app/work/users") / p["user_id"] / "novels"
        try:
            for d in base.iterdir():
                if d.name == pid:
                    state = json.loads((d / "state.json").read_text(encoding="utf-8"))
                    scene_dir = d / "scenes"
                    scene_count = len(list(scene_dir.glob("scene_*.md"))) if scene_dir.exists() else 0
                    result.append({
                        "project_id": pid,
                        "user_id": p["user_id"],
                        "display_name": p["display_name"],
                        "novel_name": state.get("novel_name", ""),
                        "current_tick": state.get("current_tick", 0),
                        "scene_count": scene_count,
                        "genre": state.get("story_foundation", {}).get("genre", ""),
                        "has_cover": _has_cover(d),
                        "created_at": p["created_at"],
                    })
                    break
        except Exception:
            continue
    return {"posts": result}


# ═══════════════════════════════════════════
# 段落评论
# ═══════════════════════════════════════════

class CommentBody(BaseModel):
    content: str
    chapter_tick: int | None = None
    paragraph: int | None = None
    parent_id: int | None = None


@router.get("/comments/{project_id}")
def list_comments(project_id: str):
    comments = _get_db().get_comments(project_id)
    for c in comments:
        if not c.get("display_name"):
            c["display_name"] = c.get("user_id", "")
    return {"comments": comments}


@router.post("/comments/{project_id}")
def add_comment(project_id: str, body: CommentBody):
    user_id = get_current_user()
    return _get_db().add_comment(
        project_id, user_id, _get_user_name(user_id),
        body.content, body.chapter_tick, body.paragraph, body.parent_id,
    )


@router.patch("/comments/{comment_id}")
def edit_comment(comment_id: int, body: CommentBody):
    """编辑评论（仅本人）。"""
    user_id = get_current_user()
    ok = _get_db().update_comment(comment_id, user_id, body.content)
    if not ok:
        raise HTTPException(status_code=403, detail="无权编辑或评论不存在")
    return {"ok": True}


@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: int):
    """删除评论（仅本人或管理员）。"""
    user_id = get_current_user()
    ok = _get_db().delete_comment(comment_id, user_id)
    if not ok:
        raise HTTPException(status_code=403, detail="无权删除或评论不存在")
    return {"ok": True}


# ═══════════════════════════════════════════
# 在线探测
# ═══════════════════════════════════════════

@router.get("/online")
def get_online():
    """在线用户数。middleware 每次请求更新 last_seen，5 分钟内活跃即在线。"""
    return {"online": _get_db().count_online_users(5)}


# ═══════════════════════════════════════════
# 聊天室（全局 + 按项目分区）
# ═══════════════════════════════════════════

class ChatBody(BaseModel):
    message: str
    project_id: str | None = None


@router.get("/chat")
def get_chat(project_id: str = None, since_id: int = 0):
    """聊天记录——project_id 为空则返回全局大厅消息。每频道最多保留 500 条。"""
    return {"messages": _get_db().get_chat_messages(project_id, since_id)}


@router.post("/chat")
def post_chat(body: ChatBody):
    user_id = get_current_user()
    msg = body.message.strip()
    if not msg or len(msg) > 2000:
        raise HTTPException(status_code=400, detail="消息不能为空或超过 2000 字")
    return _get_db().add_chat_message(user_id, _get_user_name(user_id), msg, body.project_id)
