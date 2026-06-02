"""实体浏览路由 — 角色/地点/场景/线索/势力 + 关系图。"""

import json
import shutil
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Body

from ..deps import resolve_project, try_lock_generation, release_generation
from ...cli.commands.list import (
    list_characters, list_locations, list_scenes, list_open_loops, list_factions,
)
from ...cli.commands.inspect import find_entity_file, load_entity
from ...memory.manager import MemoryManager
from ...memory.entities import Character, PhysicalTraits, Personality, CurrentState, EmotionState

logger = logging.getLogger(__name__)

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


@router.patch("/project/{project_id}/characters/{entity_id}")
def update_character(project_id: str, entity_id: str, patch: Dict[str, Any] = Body(...)):
    """Update specific fields of a character. Supports nested partial updates.
    If name fields change, performs global rename in all scene files + relations.
    """
    project_dir = resolve_project(project_id)
    memory = MemoryManager(project_dir)
    character = memory.load_character(entity_id)
    if not character:
        raise HTTPException(status_code=404, detail=f"未找到角色: {entity_id}")

    # ── Capture old names BEFORE applying changes ──
    old_family = character.family_name or ""
    old_first = character.first_name or ""
    old_full = (old_family + old_first).strip()

    # Merge nested dataclass fields
    for key, value in patch.items():
        if key == "physical_traits" and isinstance(value, dict):
            _merge_into_dataclass(character.physical_traits, value)
        elif key == "personality" and isinstance(value, dict):
            _merge_into_dataclass(character.personality, value)
        elif key == "current_state" and isinstance(value, dict):
            cs = character.current_state
            for ck, cv in value.items():
                if ck == "emotion" and isinstance(cv, dict):
                    _merge_into_dataclass(cs.emotion, cv)
                elif hasattr(cs, ck):
                    setattr(cs, ck, cv)
        elif hasattr(character, key):
            setattr(character, key, value)

    memory.save_character(character)

    # ── Detect name changes and trigger global rename ──
    new_family = character.family_name or ""
    new_first = character.first_name or ""
    new_full = (new_family + new_first).strip()
    renamed = []

    char_name = (character.family_name or "") + (character.first_name or "") or entity_id

    if old_full and new_full and old_full != new_full:
        _rename_in_project(project_dir, old_full, new_full, character_name=char_name)
        renamed.append(f"{old_full}→{new_full}")
    # Also handle individual name part changes (e.g. first name only)
    if old_first and new_first and old_first != new_first and old_first != old_full:
        _rename_in_project(project_dir, old_first, new_first, character_name=char_name)

    logger.info("Updated character %s: keys=%s rename=%s", entity_id, list(patch.keys()), renamed if renamed else "none")
    return character.to_dict()


def _merge_into_dataclass(target, updates: dict):
    """Merge dict values into a dataclass instance's attributes."""
    for k, v in updates.items():
        if hasattr(target, k):
            setattr(target, k, v)


def _extract_context(text: str, name: str, window: int = 40) -> list[dict]:
    """Find all occurrences of name in text, return [{start, end, context}]."""
    results = []
    pos = 0
    while True:
        idx = text.find(name, pos)
        if idx == -1:
            break
        ctx_start = max(0, idx - window)
        ctx_end = min(len(text), idx + len(name) + window)
        results.append({
            "start": idx,
            "end": idx + len(name),
            "context": text[ctx_start:idx] + "【" + name + "】" + text[idx + len(name):ctx_end],
        })
        pos = idx + len(name)
    return results


def _llm_verify_rename(
    project_dir: Path,
    character_name: str,
    old_name: str,
    new_name: str,
    candidates: list[dict],
) -> list[int]:
    """Use a fast LLM to verify which occurrences are genuine character name references.
    Returns indices of candidates that should be replaced.
    """
    from ...memory.manager import MemoryManager
    from ..deps import get_engine

    memory = MemoryManager(project_dir)

    # ── Gather character context: relationships ──
    rel_lines = []
    for cid in memory.list_characters():
        c = memory.load_character(cid)
        if not c or cid == character_name:
            continue
        cname = (c.family_name or "") + (c.first_name or "")
        if cname:
            rel_lines.append(f"  - {cname}（{c.role or '角色'}）")
    rel_context = "\n".join(rel_lines[:20]) if rel_lines else "（无其他角色）"

    # ── Build LLM prompt ──
    snippets = []
    for i, cand in enumerate(candidates):
        snippets.append(f"[{i}] {cand['context']}")

    prompt = f"""你是文本校对助手。角色「{character_name}」即将改名为「{new_name}」。下面是从小说中提取的包含「{old_name}」的文本片段。

已知故事中的其他角色：
{rel_context}

请判断每个片段中的「{old_name}」（用【】标记）是否确实指代角色「{character_name}」本人。
- 回答 YES：片段中的名字确实指这个角色，应替换
- 回答 NO：片段中的字串是巧合匹配（如其他词的一部分），不应替换

片段列表：
{chr(10).join(snippets)}

请只输出 JSON 数组，列出应替换的片段编号（YES 的编号）：
例如：[0, 2, 4]
如果有任何不确定的，宁可保守（选 NO）。
只输出 JSON，不要其他内容。"""

    try:
        engine = get_engine()
        model = engine.config.get("llm", {}).get("model") or "deepseek-chat"
        llm = engine.llm_pool.get_connection(backend="api", model=model)
        raw = llm.generate_with_retry(prompt, max_tokens=200)
        # Parse JSON array
        import re
        match = re.search(r"\[[\d,\s]*\]", raw)
        if match:
            return [int(n) for n in re.findall(r"\d+", match.group())]
    except Exception as exc:
        logger.warning("LLM rename verification failed, falling back to replace all: %s", exc)

    # Fallback: replace all safe-length names (2+ characters)
    if len(old_name) >= 2:
        return list(range(len(candidates)))
    return []


def _smart_replace_scene(scene_file: Path, character_name: str, old_name: str, new_name: str) -> int:
    """Replace character name in a scene file using LLM verification."""
    text = scene_file.read_text(encoding="utf-8")
    candidates = _extract_context(text, old_name)
    if not candidates:
        return 0

    # For very short names (1 char), always verify with LLM
    # For 2+ char names: if only 1-2 occurrences, replace directly; if more, use LLM
    if len(old_name) == 1 or len(candidates) > 2:
        verified = _llm_verify_rename(scene_file.parent.parent, character_name, old_name, new_name, candidates)
    else:
        verified = list(range(len(candidates)))

    if not verified:
        logger.info("LLM rejected all %d occurrences of '%s' in %s", len(candidates), old_name, scene_file.name)
        return 0

    # Apply replacements in reverse order to preserve positions
    for idx in sorted(verified, reverse=True):
        c = candidates[idx]
        text = text[:c["start"]] + new_name + text[c["end"]:]

    scene_file.write_text(text, encoding="utf-8")
    logger.info("Renamed %d/%d occurrences of '%s'→'%s' in %s", len(verified), len(candidates), old_name, new_name, scene_file.name)
    return len(verified)


def _rename_in_project(project_dir: Path, old_name: str, new_name: str, character_name: str = ""):
    """Replace all occurrences of old_name with new_name using LLM verification for prose files."""
    if not old_name or not new_name or old_name == new_name:
        return

    if not character_name:
        character_name = old_name

    replaced_count = 0

    # 1. Scene markdown files — smart LLM-verified replacement
    scenes_dir = project_dir / "scenes"
    if scenes_dir.exists():
        for scene_file in sorted(scenes_dir.glob("scene_*.md")):
            try:
                replaced_count += _smart_replace_scene(scene_file, character_name, old_name, new_name)
            except Exception:
                logger.warning("Failed to rename in %s", scene_file.name)

    # 2. Character JSON files — safe direct replace (data fields, not prose)
    chars_dir = project_dir / "memory" / "characters"
    if chars_dir.exists():
        for char_file in chars_dir.glob("*.json"):
            try:
                content = char_file.read_text(encoding="utf-8")
                if old_name in content:
                    content = content.replace(old_name, new_name)
                    char_file.write_text(content, encoding="utf-8")
                    replaced_count += 1
            except Exception:
                logger.warning("Failed to rename in %s", char_file.name)

    # 3. Plot outline — direct replace
    plot_file = project_dir / "memory" / "plot_outline.json"
    if plot_file.exists():
        try:
            text = plot_file.read_text(encoding="utf-8")
            if old_name in text:
                text = text.replace(old_name, new_name)
                plot_file.write_text(text, encoding="utf-8")
                replaced_count += 1
        except Exception:
            logger.warning("Failed to rename in plot_outline.json")

    # 4. Lore file — direct replace
    lore_file = project_dir / "memory" / "lore.json"
    if lore_file.exists():
        try:
            text = lore_file.read_text(encoding="utf-8")
            if old_name in text:
                text = text.replace(old_name, new_name)
                lore_file.write_text(text, encoding="utf-8")
                replaced_count += 1
        except Exception:
            logger.warning("Failed to rename in lore.json")

    logger.info("Global rename %s→%s: %d files updated (LLM-verified for prose)", old_name, new_name, replaced_count)


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


@router.delete("/project/{project_id}/scenes/{entity_id}")
def delete_scene(project_id: str, entity_id: str):
    """Delete a single scene — markdown, metadata, and rollback state."""
    # Prevent concurrent mutation with generation
    if not try_lock_generation(project_id):
        raise HTTPException(status_code=409, detail="该项目正在生成中，请等待完成")
    try:
        project_dir = resolve_project(project_id)
        # Find the scene — handle missing metadata gracefully
        try:
            entity = _get_entity(project_dir, entity_id)
        except HTTPException:
            # Metadata missing — try to reconstruct from filename pattern
            # Scene IDs are like "S001", extract tick number
            tick_str = entity_id[1:] if entity_id.startswith("S") else entity_id
            try:
                scene_tick = int(tick_str)
            except ValueError:
                raise HTTPException(status_code=404, detail=f"无法解析场景ID: {entity_id}")
            entity = {"tick": scene_tick}

        scene_tick = entity.get("tick", -1)
        scene_file = project_dir / "scenes" / f"scene_{scene_tick:03d}.md"
        meta_file  = project_dir / "memory" / "scenes" / f"{entity_id}.json"
        plan_file  = project_dir / "plans" / f"plan_{scene_tick:03d}.json"

        deleted = []
        for f in [scene_file, meta_file, plan_file]:
            if f.exists():
                f.unlink()
                deleted.append(str(f.name))

        # Roll back current_tick if it was the last scene
        state_file = project_dir / "state.json"
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text(encoding="utf-8"))
            except Exception:
                state = {}
            cur_tick = state.get("current_tick", 0)
            if scene_tick == cur_tick - 1:
                state["current_tick"] = max(0, scene_tick)
                from datetime import datetime
                state["last_updated"] = datetime.utcnow().isoformat() + "Z"
                state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info("Deleted scene %s (tick %d): %s", entity_id, scene_tick, ", ".join(deleted) if deleted else "nothing to delete")
        return {"deleted": entity_id, "tick": scene_tick, "files": deleted}
    finally:
        release_generation(project_id)


@router.post("/project/{project_id}/scenes/{scene_id}/rewrite")
def rewrite_scene(project_id: str, scene_id: str):
    """Rewrite a scene — rollback to its tick, backup current, and regenerate."""
    # Prevent concurrent mutation with generation
    if not try_lock_generation(project_id):
        raise HTTPException(status_code=409, detail="该项目正在生成中，请等待完成")
    try:
        project_dir = resolve_project(project_id)
        entity = _get_entity(project_dir, scene_id)
        scene_tick = entity.get("tick", -1)
        if scene_tick < 0:
            raise HTTPException(status_code=400, detail=f"无法确定场景tick: {scene_id}")

        state_file = project_dir / "state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))

        # Create a backup checkpoint before rollback
        from datetime import datetime
        backup_dir = project_dir / "checkpoints" / f"backup_before_rewrite_{scene_tick:03d}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        for sub in ["memory", "scenes", "plans"]:
            src = project_dir / sub
            if src.exists():
                dst = backup_dir / sub
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
        shutil.copy2(state_file, backup_dir / "state.json")
        logger.info("Backup saved to %s", backup_dir.name)

        # Rollback state: set current_tick to rewrite this scene
        state["current_tick"] = max(0, scene_tick)
        state["last_updated"] = datetime.utcnow().isoformat() + "Z"
        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        # Clean up scenes/plans/memory from this tick onward
        for f in project_dir.glob("scenes/scene_*.md"):
            try:
                tick_num = int(f.stem.split("_")[1])
                if tick_num >= scene_tick:
                    f.unlink()
                    logger.info("Rewrite cleanup: deleted %s", f.name)
            except (ValueError, IndexError):
                pass
        for f in project_dir.glob("memory/scenes/S*.json"):
            try:
                meta = json.loads(f.read_text(encoding="utf-8"))
                if meta.get("tick", -1) >= scene_tick:
                    f.unlink()
                    logger.info("Rewrite cleanup: deleted %s", f.name)
            except Exception:
                pass
        for f in project_dir.glob("plans/plan_*.json"):
            try:
                plan_num = int(f.stem.split("_")[1])
                if plan_num >= scene_tick:
                    f.unlink()
                    logger.info("Rewrite cleanup: deleted %s", f.name)
            except (ValueError, IndexError):
                pass

        logger.info("Rewrite complete for %s, rolled back to tick %d", scene_id, scene_tick)
        return {"rewrite": scene_id, "rollback_to": scene_tick, "backup": str(backup_dir.name)}
    finally:
        release_generation(project_id)


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
