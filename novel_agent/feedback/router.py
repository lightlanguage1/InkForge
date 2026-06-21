"""用户反馈 — 追加式 JSONL 存储，管理端查看。"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel

from ..user.context import get_current_user
from ..user.db import Database as UserDB

router = APIRouter(prefix="/api/v1/feedback", tags=["反馈"])
logger = logging.getLogger(__name__)

FEEDBACK_FILE = Path("work/feedback.jsonl")


class FeedbackBody(BaseModel):
    title: str
    content: str = ""
    category: str = "建议"


def _append(entry: dict):
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_all() -> list[dict]:
    if not FEEDBACK_FILE.exists():
        return []
    entries = []
    with open(FEEDBACK_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return list(reversed(entries))  # 最新在前


# ═══════════════════════════════════════════
# 公开 — 提交反馈
# ═══════════════════════════════════════════

@router.post("/")
async def submit(body: FeedbackBody, request: Request):
    """提交反馈（需登录）。"""
    user_id = get_current_user()
    user = UserDB().get_user(user_id) if user_id else None
    display_name = user.get("display_name", user_id) if user else (user_id or "匿名")

    entry = {
        "id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "_" + (user_id or "anon")[:8],
        "user_id": user_id or "anon",
        "display_name": display_name,
        "title": body.title.strip(),
        "content": body.content.strip(),
        "category": body.category,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _append(entry)
    logger.info("反馈已记录: %s", body.title)
    return {"ok": True, "id": entry["id"]}


# ═══════════════════════════════════════════
# 管理 — 查看/更新
# ═══════════════════════════════════════════

@router.get("/")
def list_feedback(_admin: str = "", status: str = Query("", description="open | closed | all")):
    """管理端：查看反馈列表。"""
    _require_admin()
    entries = _read_all()
    if status and status != "all":
        entries = [e for e in entries if e.get("status") == status]
    return {"feedback": entries}


class FeedbackUpdate(BaseModel):
    status: str = ""
    admin_note: str = ""


@router.patch("/{feedback_id}")
def update_feedback(feedback_id: str, body: FeedbackUpdate):
    """管理端：更新反馈状态/备注。"""
    _require_admin()
    entries = []
    updated = False
    if FEEDBACK_FILE.exists():
        with open(FEEDBACK_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("id") == feedback_id:
                    if body.status:
                        entry["status"] = body.status
                    if body.admin_note:
                        entry["admin_note"] = body.admin_note
                    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
                    updated = True
                entries.append(entry)
    if not updated:
        raise HTTPException(status_code=404, detail="反馈不存在")
    FEEDBACK_FILE.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n", encoding="utf-8")
    return {"ok": True}


def _require_admin():
    user_id = get_current_user()
    user = UserDB().get_user(user_id)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return True
