"""实体浏览路由 — 角色/地点/场景/线索/势力。"""

from fastapi import APIRouter, HTTPException
from pathlib import Path

from ..deps import resolve_project
from ...cli.commands.list import (
    list_characters, list_locations, list_scenes, list_open_loops, list_factions,
)
from ...cli.commands.inspect import find_entity_file, load_entity

router = APIRouter(prefix="/api/v1", tags=["实体"])


def _get_entity(project_dir: Path, entity_id: str) -> dict:
    path = find_entity_file(project_dir, entity_id)
    if path is None:
        raise HTTPException(status_code=404, detail=f"未找到实体: {entity_id}")
    entity = load_entity(path)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"无法加载: {entity_id}")
    return entity


# ---- 角色 ----

@router.get("/project/{project_id}/characters")
def get_characters(project_id: str, verbose: bool = False):
    return {"characters": list_characters(resolve_project(project_id), verbose=verbose)}


@router.get("/project/{project_id}/characters/{entity_id}")
def get_character(project_id: str, entity_id: str):
    return _get_entity(resolve_project(project_id), entity_id)


# ---- 地点 ----

@router.get("/project/{project_id}/locations")
def get_locations(project_id: str, verbose: bool = False):
    return {"locations": list_locations(resolve_project(project_id), verbose=verbose)}


@router.get("/project/{project_id}/locations/{entity_id}")
def get_location(project_id: str, entity_id: str):
    return _get_entity(resolve_project(project_id), entity_id)


# ---- 场景 ----

@router.get("/project/{project_id}/scenes")
def get_scenes(project_id: str, verbose: bool = False):
    return {"scenes": list_scenes(resolve_project(project_id), verbose=verbose)}


@router.get("/project/{project_id}/scenes/{entity_id}")
def get_scene(project_id: str, entity_id: str):
    return _get_entity(resolve_project(project_id), entity_id)


# ---- 线索 ----

@router.get("/project/{project_id}/loops")
def get_loops(project_id: str, verbose: bool = False):
    return {"loops": list_open_loops(resolve_project(project_id), verbose=verbose)}


# ---- 势力 ----

@router.get("/project/{project_id}/factions")
def get_factions(project_id: str, verbose: bool = False):
    return {"factions": list_factions(resolve_project(project_id), verbose=verbose)}


@router.get("/project/{project_id}/factions/{entity_id}")
def get_faction(project_id: str, entity_id: str):
    return _get_entity(resolve_project(project_id), entity_id)
