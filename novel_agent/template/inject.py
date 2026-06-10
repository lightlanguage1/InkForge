"""低耦合注入 — 失败返回空字符串，不影响核心。"""

import logging

logger = logging.getLogger(__name__)

_db = None


def _get_db():
    global _db
    if _db is None:
        from .db import TemplateDB
        _db = TemplateDB()
    return _db


def get_style_context(project_state: dict) -> str:
    """从项目状态读取 style_id，返回 prompt_snippet。"""
    try:
        style_id = project_state.get("style_id", "")
        if not style_id:
            return ""
        template = _get_db().get_by_id("style", style_id)
        if template and template.get("prompt_snippet"):
            return template["prompt_snippet"]
    except Exception as e:
        logger.debug("style注入跳过: %s", e)
    return ""


def get_craft_context(project_state: dict) -> str:
    """从项目状态读取 craft_id，返回 prompt_snippet。"""
    try:
        craft_id = project_state.get("craft_id", "")
        if not craft_id:
            return ""
        template = _get_db().get_by_id("craft", craft_id)
        if template and template.get("prompt_snippet"):
            return template["prompt_snippet"]
    except Exception as e:
        logger.debug("craft注入跳过: %s", e)
    return ""


def set_project_style(project_state: dict, style_id: str = "", craft_id: str = "") -> dict:
    """设置项目的文风和写作方法 ID，返回更新后的 state。"""
    project_state["style_id"] = style_id
    project_state["craft_id"] = craft_id
    return project_state
