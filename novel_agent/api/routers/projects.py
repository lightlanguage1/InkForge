"""项目生命周期路由。"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ...utils.log_manager import rmtree_force

from ..deps import get_engine, get_novels_dir, resolve_project, create_agent
from ..models import ProjectCreateRequest, TickRequest, TickResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["项目"])


def _list_filesystem_projects() -> list[dict]:
    """扫描用户 novels 目录，返回所有有效项目。"""
    novels = get_novels_dir()
    if not novels.exists():
        return []
    projects = []
    for entry in sorted(novels.iterdir(), reverse=True):
        if not entry.is_dir():
            continue
        state_file = entry / "state.json"
        if not state_file.exists():
            continue
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        projects.append({
            "project_path": str(entry.resolve()),
            "project_id": state.get("project_id", entry.name),
            "novel_name": state.get("novel_name", entry.name),
            "current_tick": state.get("current_tick", 0),
        })
    return projects


# ---- 创建 / 列表 / 恢复 ----

@router.post("/project")
def create_project(req: ProjectCreateRequest):
    engine = get_engine()
    # Force user-scoped directory, never use legacy global novels_dir
    user_novels_dir = str(get_novels_dir())
    try:
        path = engine.create_project(
            name=req.name, directory=user_novels_dir,
            genre=req.genre, premise=req.premise,
            protagonist=req.protagonist, setting=req.setting,
            tone=req.tone, themes=req.themes,
            use_plot_first=req.use_plot_first,
        )
    except Exception:
        logger.exception("创建项目失败: %s", req.name)
        raise HTTPException(status_code=500, detail="创建项目失败")

    # 自动注入选中的写作技能
    if req.skill_ids:
        applied = []
        store = engine.skill_store
        skills = [s for sid in req.skill_ids if (s := store.load_skill(sid))]
        if skills:
            from ...skill.injector import SkillInjector
            injector = SkillInjector(project_path=path, config=engine.config)
            injector.inject(skills, mode="reference")
            applied = [s.name for s in skills]
        return {"project_path": path, "skills_applied": applied}

    return {"project_path": path}


@router.get("/projects")
def list_projects():
    return {"projects": _list_filesystem_projects()}


@router.post("/resume")
def resume():
    from ...cli.recent_projects import RecentProjects
    from ...cli.project import load_project_state

    # 优先 RecentProjects 追踪
    recent = RecentProjects()
    path = recent.get_most_recent()
    if path:
        state = load_project_state(Path(path))
        return {
            "project_path": path,
            "project_id": state.get("project_id", ""),
            "novel_name": state.get("novel_name", ""),
            "current_tick": state.get("current_tick", 0),
        }

    # fallback: 扫描目录取最新
    projects = _list_filesystem_projects()
    if projects:
        p = projects[0]
        return {
            "project_path": p["project_path"],
            "project_id": p["project_id"],
            "novel_name": p["novel_name"],
            "current_tick": p["current_tick"],
        }

    raise HTTPException(status_code=404, detail="没有找到任何项目，请先创建项目或运行 novel tick")


# ---- 删除 ----

@router.delete("/project/{project_id}")
def delete_project(project_id: str):
    try:
        project_dir = resolve_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"项目不存在: {project_id}")
    try:
        rmtree_force(project_dir)
    except OSError as exc:
        logger.exception("删除项目失败: %s", project_dir)
        raise HTTPException(status_code=500, detail=f"删除失败: {exc}")
    return {"deleted": str(project_dir)}


# ---- Tick ----

@router.post("/project/{project_id}/tick", response_model=TickResponse)
def run_tick(project_id: str, req: TickRequest = None):
    from .generation import _try_lock, _release
    if not _try_lock(project_id):
        raise HTTPException(status_code=409, detail="该项目正在生成中，请等待完成")
    try:
        if req is None:
            req = TickRequest()
        project_dir = resolve_project(project_id)
        agent = create_agent(
            project_dir,
            llm_backend=req.llm_backend,
            llm_model=req.llm_model,
            save_prompts=req.save_prompts,
        )
        result = agent.tick(notes=req.notes or "")
    except HTTPException:
        _release(project_id)
        raise
    except Exception:
        _release(project_id)
        logger.exception("Tick 失败: project=%s", project_id)
        raise HTTPException(status_code=500, detail="故事生成失败，请查看服务端日志")
    _release(project_id)
    return TickResponse(
        success=True,
        tick=result.get("tick", 0),
        scene_id=result.get("scene_id", ""),
        scene_file=result.get("scene_file", ""),
        word_count=result.get("word_count", 0),
        actions_executed=result.get("actions_executed", 0),
        tension=result.get("tension"),
    )
