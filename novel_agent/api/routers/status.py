"""项目信息路由 — status / goals / lore。"""

from typing import Optional

from fastapi import APIRouter, Query

from ..deps import resolve_project
from ...cli.project import load_project_state
from ...cli.commands.goals import get_goals_info
from ...cli.commands.lore import get_lore_info
from ...memory.manager import MemoryManager

router = APIRouter(prefix="/api/v1", tags=["信息"])


@router.get("/project/{project_id}/status")
def get_status(project_id: str):
    from .generation import _running
    project_dir = resolve_project(project_id)
    state = load_project_state(str(project_dir))
    memory = MemoryManager(project_dir)

    scenes = memory.list_scenes()
    total = 0
    tensions = []
    for sid in scenes:
        s = memory.load_scene(sid)
        if s:
            total += s.word_count or 0
            if s.tension_level is not None:
                tensions.append(s.tension_level)

    return {
        "project_id": project_id,
        "current_tick": state.get("current_tick", 0),
        "novel_name": state.get("novel_name", "Untitled"),
        "scene_count": len(scenes),
        "character_count": len(memory.list_characters()),
        "location_count": len(memory.list_locations()),
        "faction_count": len(memory.list_factions()),
        "open_loops_count": len(memory.load_open_loops()),
        "lore_count": len(memory.load_all_lore()),
        "word_count": total,
        "avg_tension": sum(tensions) / len(tensions) if tensions else 0,
        "generating": project_id in _running,
    }


@router.get("/project/{project_id}/goals")
def get_goals(project_id: str):
    project_dir = resolve_project(project_id)
    state = load_project_state(str(project_dir))
    return get_goals_info(project_dir, state)


@router.get("/project/{project_id}/lore")
def get_lore(
    project_id: str,
    category: Optional[str] = Query(None),
    lore_type: Optional[str] = Query(None),
    importance: Optional[str] = Query(None),
):
    project_dir = resolve_project(project_id)
    result = get_lore_info(project_dir)
    lore_list = result.get("all_lore", [])
    if category:
        lore_list = [l for l in lore_list if l.get("category") == category]
    if lore_type:
        lore_list = [l for l in lore_list if l.get("type") == lore_type]
    if importance:
        lore_list = [l for l in lore_list if l.get("importance") == importance]
    return {
        "total_count": len(lore_list),
        "importance_counts": result.get("importance_counts", {}),
        "lore": lore_list,
    }
