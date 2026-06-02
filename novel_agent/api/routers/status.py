"""项目信息路由 — status / goals / lore。"""

import logging
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from ..deps import resolve_project
from ...cli.project import load_project_state
from ...cli.commands.goals import get_goals_info
from ...cli.commands.lore import get_lore_info
from ...memory.manager import MemoryManager

logger = logging.getLogger(__name__)
from ...utils.file_ops import write_json

router = APIRouter(prefix="/api/v1", tags=["信息"])


class FoundationPatch(BaseModel):
    tone: Optional[str] = None
    genre: Optional[str] = None
    premise: Optional[str] = None
    setting: Optional[str] = None


@router.patch("/project/{project_id}/foundation")
def patch_foundation(project_id: str, patch: FoundationPatch):
    """Update writable fields in story_foundation."""
    project_dir = resolve_project(project_id)
    state_file = project_dir / "state.json"
    import json
    state = json.loads(state_file.read_text(encoding="utf-8"))
    foundation = state.setdefault("story_foundation", {})
    updates = patch.model_dump(exclude_none=True)
    foundation.update(updates)
    write_json(str(state_file), state)
    return {"updated": list(updates.keys())}


@router.get("/project/{project_id}/status")
def get_status(project_id: str):
    from ..deps import is_generation_running
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
        "generating": is_generation_running(project_id),
        "genre": (state.get("story_foundation") or {}).get("genre", ""),
        "tone":  (state.get("story_foundation") or {}).get("tone",  ""),
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


# ── Lore CRUD ──────────────────────────────────────────────────────────────

class LorePatch(BaseModel):
    content: Optional[str] = None
    category: Optional[str] = None
    lore_type: Optional[str] = None
    importance: Optional[str] = None
    tags: Optional[list] = None


class LoreCreate(BaseModel):
    content: str
    category: str = ""
    lore_type: str = "rule"
    importance: str = "normal"
    tags: list = []


@router.patch("/project/{project_id}/lore/{lore_id}")
def update_lore(project_id: str, lore_id: str, patch: LorePatch):
    """Update a lore entry's fields."""
    project_dir = resolve_project(project_id)
    memory = MemoryManager(project_dir)
    lore = memory.load_lore(lore_id)
    if not lore:
        raise HTTPException(status_code=404, detail=f"未找到世界观条目: {lore_id}")

    updates = patch.model_dump(exclude_none=True)
    for key, value in updates.items():
        if hasattr(lore, key):
            setattr(lore, key, value)
    memory.save_lore(lore)
    logger.info("Updated lore %s: %s", lore_id, list(updates.keys()))
    return lore.to_dict()


@router.post("/project/{project_id}/lore")
def create_lore(project_id: str, body: LoreCreate):
    """Create a new lore entry."""
    project_dir = resolve_project(project_id)
    memory = MemoryManager(project_dir)
    from ...memory.entities import Lore as LoreEntity
    lore_id = memory.generate_lore_id()
    lore = LoreEntity(
        id=lore_id,
        lore_type=body.lore_type,
        content=body.content,
        category=body.category,
        importance=body.importance,
        tags=body.tags or [],
        source_scene_id="manual",
        tick=0,
    )
    memory.save_lore(lore)
    logger.info("Created lore %s: %s", lore_id, body.content[:40])
    return lore.to_dict()


@router.delete("/project/{project_id}/lore/{lore_id}")
def delete_lore(project_id: str, lore_id: str):
    """Delete a lore entry."""
    project_dir = resolve_project(project_id)
    memory = MemoryManager(project_dir)
    lore = memory.load_lore(lore_id)
    if not lore:
        raise HTTPException(status_code=404, detail=f"未找到世界观条目: {lore_id}")
    memory.delete_lore(lore_id)
    logger.info("Deleted lore %s", lore_id)
    return {"deleted": lore_id}
