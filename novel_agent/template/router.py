"""文风 & 写作方法模板 API。"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .db import TemplateDB
from .presets import install_presets
from ..user.context import get_current_user
from ..user.db import Database as UserDB

router = APIRouter(prefix="/api/v1", tags=["模板"])
logger = logging.getLogger(__name__)

_db: TemplateDB | None = None


def _tdb() -> TemplateDB:
    global _db
    if _db is None:
        _db = TemplateDB()
        install_presets(_db)
    return _db


def _require_admin():
    user_id = get_current_user()
    user = UserDB().get_user(user_id)
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")


# ═══════════════════════════════════════════
# 预设
# ═══════════════════════════════════════════

@router.get("/styles/presets")
def list_style_presets():
    return {"templates": _tdb().get_presets("style")}


@router.get("/craft/presets")
def list_craft_presets():
    return {"templates": _tdb().get_presets("craft")}


# ═══════════════════════════════════════════
# 用户模板（文风）
# ═══════════════════════════════════════════

class TemplateBody(BaseModel):
    name: str
    description: str = ""
    prompt_snippet: str = ""


@router.get("/styles/templates")
def list_style_templates():
    user_id = get_current_user()
    return {"templates": _tdb().list_user("style", user_id)}


@router.post("/styles/templates")
def create_style(body: TemplateBody):
    user_id = get_current_user()
    tid = _tdb().create(body.name, body.description, body.prompt_snippet, "style", user_id)
    return {"ok": True, "id": tid}


@router.patch("/styles/templates/{template_id}")
def update_style(template_id: str, body: TemplateBody):
    user_id = get_current_user()
    ok = _tdb().update("style", template_id, user_id, body.name, body.description, body.prompt_snippet)
    if not ok:
        raise HTTPException(status_code=404, detail="模板不存在或无权修改")
    return {"ok": True}


@router.delete("/styles/templates/{template_id}")
def delete_style(template_id: str):
    user_id = get_current_user()
    ok = _tdb().delete("style", template_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="模板不存在或无权删除")
    return {"ok": True}


# ═══════════════════════════════════════════
# 用户模板（写作方法）
# ═══════════════════════════════════════════

@router.get("/craft/templates")
def list_craft_templates():
    user_id = get_current_user()
    return {"templates": _tdb().list_user("craft", user_id)}


@router.post("/craft/templates")
def create_craft(body: TemplateBody):
    user_id = get_current_user()
    tid = _tdb().create(body.name, body.description, body.prompt_snippet, "craft", user_id)
    return {"ok": True, "id": tid}


@router.patch("/craft/templates/{template_id}")
def update_craft(template_id: str, body: TemplateBody):
    user_id = get_current_user()
    ok = _tdb().update("craft", template_id, user_id, body.name, body.description, body.prompt_snippet)
    if not ok:
        raise HTTPException(status_code=404, detail="模板不存在或无权修改")
    return {"ok": True}


@router.delete("/craft/templates/{template_id}")
def delete_craft(template_id: str):
    user_id = get_current_user()
    ok = _tdb().delete("craft", template_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="模板不存在或无权删除")
    return {"ok": True}


# ═══════════════════════════════════════════
# 公开共享
# ═══════════════════════════════════════════

@router.get("/styles/public")
def list_style_public():
    return {"templates": _tdb().get_public("style")}


@router.get("/craft/public")
def list_craft_public():
    return {"templates": _tdb().get_public("craft")}


# ═══════════════════════════════════════════
# 项目配置（admin only for presets, project owner for self）
# ═══════════════════════════════════════════

class ProjectStyleConfig(BaseModel):
    style_id: str = ""
    craft_id: str = ""


@router.patch("/project/{project_id}/style-config")
def set_project_style(project_id: str, body: ProjectStyleConfig):
    """设置项目的文风和写作方法模板。"""
    from pathlib import Path
    import json

    user_id = get_current_user()
    base = Path("/app/work/users") / user_id / "novels"

    # 找项目目录
    state_path = None
    if base.exists():
        for d in base.iterdir():
            if d.is_dir() and d.name.endswith(f"_{project_id}"):
                state_path = d / "state.json"
                break

    if not state_path or not state_path.exists():
        raise HTTPException(status_code=404, detail="项目不存在")

    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["style_id"] = body.style_id
    state["craft_id"] = body.craft_id
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "style_id": body.style_id, "craft_id": body.craft_id}


@router.get("/project/{project_id}/style-config")
def get_project_style(project_id: str):
    """读取项目的文风和写作方法配置。"""
    from pathlib import Path
    import json

    user_id = get_current_user()
    base = Path("/app/work/users") / user_id / "novels"

    state_path = None
    if base.exists():
        for d in base.iterdir():
            if d.is_dir() and d.name.endswith(f"_{project_id}"):
                state_path = d / "state.json"
                break

    style_id = ""; craft_id = ""
    if state_path and state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        style_id = state.get("style_id", "")
        craft_id = state.get("craft_id", "")

    return {"style_id": style_id, "craft_id": craft_id}
