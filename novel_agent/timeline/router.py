"""时间线 & 分支管理 API — 独立模块。"""

import logging

from fastapi import APIRouter, HTTPException

from ..api.deps import resolve_project
from ..memory.branch_manager import build_timeline, switch_branch as do_switch

router = APIRouter(prefix="/api/v1", tags=["时间线"])
logger = logging.getLogger(__name__)


@router.get("/project/{project_id}/timeline")
def get_timeline(project_id: str):
    """返回完整时间线——主干 + 分支 + 存档点，git graph 结构。"""
    return build_timeline(resolve_project(project_id))


@router.post("/project/{project_id}/switch-branch/{branch_name}")
def switch_branch(project_id: str, branch_name: str):
    """切换到指定分支——git checkout <branch>"""
    try:
        return do_switch(resolve_project(project_id), branch_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
