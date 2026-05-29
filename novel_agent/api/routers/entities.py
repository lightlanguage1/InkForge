"""实体浏览路由 — 角色/地点/场景/线索/势力 + 关系图。"""

from fastapi import APIRouter, HTTPException
from pathlib import Path

from ..deps import resolve_project
from ...cli.commands.list import (
    list_characters, list_locations, list_scenes, list_open_loops, list_factions,
)
from ...cli.commands.inspect import find_entity_file, load_entity
from ...memory.manager import MemoryManager

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


@router.get("/project/{project_id}/relationships")
def get_relationships(project_id: str):
    project_dir = resolve_project(project_id)
    memory = MemoryManager(project_dir)
    char_ids = memory.list_characters()

    # 构建 ID→名字 和 名字→ID 双向映射
    name_map: dict[str, str] = {}
    name_to_id: dict[str, str] = {}
    nodes = []
    for cid in char_ids:
        char = memory.load_character(cid)
        if not char:
            continue
        full = (char.family_name or "") + (char.first_name or "")
        display = full or cid
        name_map[cid] = display
        name_to_id[display] = cid
        nodes.append({"id": cid, "name": display, "status": getattr(char, "status", "active") or "active"})

    def _resolve_id(raw: str) -> str | None:
        """将 character_b 解析为角色 ID（支持直接 ID 和中文名）。"""
        if raw in name_map:
            return raw
        return name_to_id.get(raw)

    def _str_status(s: object) -> str:
        if isinstance(s, dict):
            return s.get("new") or s.get("old") or ""
        return str(s) if s else ""

    # 从 relationships.json 读取全局关系（这里才是真正的边数据）
    all_rels = memory.load_relationships()
    edges = []
    seen: set[tuple[str, str]] = set()
    for rel in all_rels:
        src = _resolve_id(rel.character_a)
        tgt = _resolve_id(rel.character_b)
        if not src or not tgt or src == tgt:
            continue
        key = tuple(sorted([src, tgt]))
        if key in seen:
            continue
        seen.add(key)
        edges.append({
            "source": src,
            "target": tgt,
            "sourceName": name_map.get(src, src),
            "targetName": name_map.get(tgt, tgt),
            "type": rel.relationship_type or "",
            "status": _str_status(rel.status),
            "description": _str_status(rel.perspective_a),
        })

    # 连通分量 BFS + 度数
    adj: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for e in edges:
        adj[e["source"]].append(e["target"])
        adj[e["target"]].append(e["source"])
    visited: set[str] = set()
    component: dict[str, int] = {}
    comp_idx = 0
    for n in nodes:
        if n["id"] in visited:
            continue
        queue = [n["id"]]
        visited.add(n["id"])
        while queue:
            cur = queue.pop(0)
            component[cur] = comp_idx
            for nb in adj.get(cur, []):
                if nb not in visited:
                    visited.add(nb)
                    queue.append(nb)
        comp_idx += 1

    for n in nodes:
        n["degree"] = len(adj.get(n["id"], []))
        n["colorGroup"] = component.get(n["id"], 0)

    return {"nodes": nodes, "edges": edges}
