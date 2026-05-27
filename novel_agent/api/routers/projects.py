"""项目生命周期路由。"""

from fastapi import APIRouter, HTTPException

from ..deps import get_engine, resolve_project, create_agent
from ..models import ProjectCreateRequest, TickRequest, TickResponse

router = APIRouter(prefix="/api/v1", tags=["项目"])


# ---- 创建 / 列表 / 恢复 ----

@router.post("/project")
def create_project(req: ProjectCreateRequest):
    engine = get_engine()
    path = engine.create_project(
        name=req.name, directory=req.directory,
        genre=req.genre, premise=req.premise,
        protagonist=req.protagonist, setting=req.setting,
        tone=req.tone, themes=req.themes,
        use_plot_first=req.use_plot_first,
    )
    return {"project_path": path}


@router.get("/projects")
def list_projects():
    engine = get_engine()
    return {"projects": engine.project_manager.get_active_projects()}


@router.post("/resume")
def resume():
    from ...cli.recent_projects import RecentProjects
    from ...cli.project import load_project_state
    from pathlib import Path

    recent = RecentProjects()
    path = recent.get_most_recent()
    if not path:
        raise HTTPException(status_code=404, detail="没有最近项目")
    state = load_project_state(Path(path))
    return {
        "project_path": path,
        "project_id": state.get("project_id", ""),
        "novel_name": state.get("novel_name", ""),
        "current_tick": state.get("current_tick", 0),
    }


# ---- Tick / Run ----

@router.post("/project/{project_id}/tick", response_model=TickResponse)
def run_tick(project_id: str, req: TickRequest = None):
    if req is None:
        req = TickRequest()
    project_dir = resolve_project(project_id)
    try:
        agent = create_agent(
            project_dir,
            llm_backend=req.llm_backend, llm_model=req.llm_model,
            save_prompts=req.save_prompts,
        )
        result = agent.tick(notes=req.notes or "")
        return TickResponse(
            success=True,
            tick=result.get("tick", 0),
            scene_id=result.get("scene_id", ""),
            scene_file=result.get("scene_file", ""),
            word_count=result.get("word_count", 0),
            actions_executed=result.get("actions_executed", 0),
            tension=result.get("tension"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
