"""实体浏览路由 — 角色/地点/场景/线索/势力 + 关系图。"""

import json
import shutil
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

from ..deps import resolve_project, try_lock_generation, release_generation
from ...cli.commands.list import (
    list_characters, list_locations, list_scenes, list_open_loops, list_factions,
)
from ...cli.commands.inspect import find_entity_file, load_entity
from ...memory.manager import MemoryManager
from ...memory.entities import Character, PhysicalTraits, Personality, CurrentState, EmotionState
from ...tools.registry import ToolRegistry

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


@router.delete("/project/{project_id}/characters/{entity_id}")
def delete_character(project_id: str, entity_id: str):
    """Delete a character and clean up all references."""
    if not try_lock_generation(project_id):
        raise HTTPException(status_code=409, detail="该项目正在生成中，请等待完成")
    try:
        project_dir = resolve_project(project_id)
        memory = MemoryManager(project_dir)
        character = memory.load_character(entity_id)
        if not character:
            raise HTTPException(status_code=404, detail=f"未找到角色: {entity_id}")

        char_name = (character.family_name or "") + (character.first_name or "")
        cleaned = {"relationships": 0, "state": False, "character_file": False}

        # 1. Remove this character from all other characters' relationships
        for cid in memory.list_characters():
            if cid == entity_id:
                continue
            other = memory.load_character(cid)
            if not other or not other.relationships:
                continue
            before = len(other.relationships)
            other.relationships = [r for r in other.relationships if r.character_id != entity_id]
            if len(other.relationships) < before:
                memory.save_character(other)
                cleaned["relationships"] += 1

        # 2. Clean relationships.json global file
        all_rels = memory.load_relationships()
        before_rels = len(all_rels)
        all_rels = [r for r in all_rels if r.character_a != entity_id and r.character_b != entity_id]
        if len(all_rels) < before_rels:
            from ...memory.manager import MemoryManager as MM
            data = {"relationships": [r.to_dict() for r in all_rels]}
            (project_dir / "memory" / "relationships.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        # 3. Update state.json if deleted character was active
        state_file = project_dir / "state.json"
        if state_file.exists():
            state = json.loads(state_file.read_text(encoding="utf-8"))
            if state.get("active_character") == entity_id:
                state["active_character"] = None
                from datetime import datetime
                state["last_updated"] = datetime.utcnow().isoformat() + "Z"
                state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
                cleaned["state"] = True

        # 4. Delete character JSON file
        char_file = project_dir / "memory" / "characters" / f"{entity_id}.json"
        if char_file.exists():
            char_file.unlink()
            cleaned["character_file"] = True

        memory.invalidate_cache()
        logger.info("Deleted character %s (%s): cleaned=%s", entity_id, char_name, cleaned)
        return {"deleted": entity_id, "name": char_name, "cleaned": cleaned}
    finally:
        release_generation(project_id)


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

    # 5. Faction JSON — direct replace (descriptions, stances may mention characters)
    factions_dir = project_dir / "memory" / "factions"
    if factions_dir.exists():
        for faction_file in factions_dir.glob("*.json"):
            try:
                content = faction_file.read_text(encoding="utf-8")
                if old_name in content:
                    content = content.replace(old_name, new_name)
                    faction_file.write_text(content, encoding="utf-8")
                    replaced_count += 1
            except Exception:
                logger.warning("Failed to rename in %s", faction_file.name)

    # 6. Location JSON — direct replace (descriptions may mention characters)
    locs_dir = project_dir / "memory" / "locations"
    if locs_dir.exists():
        for loc_file in locs_dir.glob("*.json"):
            try:
                content = loc_file.read_text(encoding="utf-8")
                if old_name in content:
                    content = content.replace(old_name, new_name)
                    loc_file.write_text(content, encoding="utf-8")
                    replaced_count += 1
            except Exception:
                logger.warning("Failed to rename in %s", loc_file.name)

    # 7. Relationships JSON — direct replace
    rels_file = project_dir / "memory" / "relationships.json"
    if rels_file.exists():
        try:
            text = rels_file.read_text(encoding="utf-8")
            if old_name in text:
                text = text.replace(old_name, new_name)
                rels_file.write_text(text, encoding="utf-8")
                replaced_count += 1
        except Exception:
            logger.warning("Failed to rename in relationships.json")

    logger.info("Global rename %s→%s: %d files updated (LLM-verified for prose)", old_name, new_name, replaced_count)


# ---- 地点 ----

@router.get("/project/{project_id}/locations")
def get_locations(project_id: str, verbose: bool = False):
    return {"locations": list_locations(resolve_project(project_id), verbose=verbose)}


@router.get("/project/{project_id}/locations/{entity_id}")
def get_location(project_id: str, entity_id: str):
    return _get_entity(resolve_project(project_id), entity_id)


@router.patch("/project/{project_id}/locations/{entity_id}")
def update_location(project_id: str, entity_id: str, patch: Dict[str, Any] = Body(...)):
    project_dir = resolve_project(project_id)
    memory = MemoryManager(project_dir)
    try:
        memory.update_location(entity_id, patch)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return memory.load_location(entity_id).to_dict()


@router.delete("/project/{project_id}/locations/{entity_id}")
def delete_location(project_id: str, entity_id: str):
    project_dir = resolve_project(project_id)
    memory = MemoryManager(project_dir)
    if not memory.load_location(entity_id):
        raise HTTPException(status_code=404, detail=f"未找到地点: {entity_id}")
    memory.delete_location(entity_id)
    return {"deleted": entity_id}


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

        # 用剩余场景重建所有实体的动态状态
        try:
            memory = MemoryManager(project_dir)
            memory.rebuild_all_after_scene_delete(entity_id)
        except Exception as e:
            logger.warning("场景 %s 已删除，但重建实体数据失败（不影响删除结果）: %s", entity_id, e)

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


@router.get("/project/{project_id}/loops/{entity_id}")
def get_loop(project_id: str, entity_id: str):
    return _get_entity(resolve_project(project_id), entity_id)


@router.patch("/project/{project_id}/loops/{entity_id}")
def update_loop(project_id: str, entity_id: str, patch: Dict[str, Any] = Body(...)):
    project_dir = resolve_project(project_id)
    memory = MemoryManager(project_dir)
    memory.update_open_loop(entity_id, patch)
    loops = memory.load_open_loops()
    loop = next((l for l in loops if l.id == entity_id), None)
    if not loop:
        raise HTTPException(status_code=404, detail=f"未找到线索: {entity_id}")
    return loop.to_dict()


@router.delete("/project/{project_id}/loops/{entity_id}")
def delete_loop(project_id: str, entity_id: str):
    project_dir = resolve_project(project_id)
    memory = MemoryManager(project_dir)
    memory.delete_open_loop(entity_id)
    return {"deleted": entity_id}


# ---- 势力 ----

@router.get("/project/{project_id}/factions")
def get_factions(project_id: str, verbose: bool = False):
    return {"factions": list_factions(resolve_project(project_id), verbose=verbose)}


@router.get("/project/{project_id}/factions/{entity_id}")
def get_faction(project_id: str, entity_id: str):
    return _get_entity(resolve_project(project_id), entity_id)


@router.patch("/project/{project_id}/factions/{entity_id}")
def update_faction(project_id: str, entity_id: str, patch: Dict[str, Any] = Body(...)):
    """更新势力字段。"""
    project_dir = resolve_project(project_id)
    memory = MemoryManager(project_dir)
    faction = memory.load_faction(entity_id)
    if not faction:
        raise HTTPException(status_code=404, detail=f"未找到势力: {entity_id}")
    for key, val in patch.items():
        if hasattr(faction, key):
            setattr(faction, key, val)
    memory.save_faction(faction)
    return faction.to_dict()


@router.delete("/project/{project_id}/factions/{entity_id}")
def delete_faction(project_id: str, entity_id: str):
    """删除势力。"""
    project_dir = resolve_project(project_id)
    memory = MemoryManager(project_dir)
    if not memory.load_faction(entity_id):
        raise HTTPException(status_code=404, detail=f"未找到势力: {entity_id}")
    memory.delete_faction(entity_id)
    return {"deleted": entity_id}


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


# ---- 设定导入 ----

class ImportRequest(BaseModel):
    content: str = ""          # MD/TXT 文本内容
    confirm: bool = False      # false=仅预览, true=执行导入
    entities: list = []        # confirm=true 时传入用户编辑后的实体列表


def _parse_document(content: str) -> list:
    """用 LLM 解析文档，返回识别到的实体列表。"""
    prompt = (
        "你是一个小说设定解析器。分析以下文档，提取所有角色、地点、阵营组织。\n\n"
        "为每个实体生成一个 JSON 对象：\n"
        '- 角色: {"type":"character","args":{"name":"中文名","role":"主角/配角/反派","description":"...","traits":[],"goals":[]}}\n'
        '- 地点: {"type":"location","args":{"name":"","description":"","atmosphere":"","features":[]}}\n'
        '- 阵营: {"type":"faction","args":{"name":"","org_type":"","summary":""}}\n\n'
        "返回纯 JSON 数组，不要解释：\n"
        '[{"type":"character","args":{...}},{"type":"location","args":{...}}]\n\n'
        f"文档内容：\n{content}"
    )
    import re
    from ...tools.llm_interface import send_prompt
    response = send_prompt(prompt, max_tokens=3000)
    json_match = re.search(r'\[[\s\S]*\]', response)
    if not json_match:
        raise ValueError("LLM 返回格式异常，无法解析")
    return json.loads(json_match.group())


# ── 智能去重合并 ──

def _norm(name: str) -> str:
    """标准化名称用于匹配：去括号注释、去空格、小写。"""
    import re
    n = re.sub(r'[（(][^)）]*[)）]', '', name)  # 去括号注释
    n = re.sub(r'\s+', '', n)  # 去所有空白
    return n.lower()


def _names_match(a: str, b: str) -> bool:
    """两个名称是否指向同一个实体。"""
    na = _norm(a)
    nb = _norm(b)
    if na == nb:
        return True
    # 包含匹配："沈青鸿" vs "沈青鸿（核爆仙尊）"
    if na in nb or nb in na:
        return True
    return False


def _merge_str(old_val: str, new_val: str) -> str:
    """合并字符串字段：取更长的（信息更完整）。"""
    if not new_val:
        return old_val
    if not old_val:
        return new_val
    return new_val if len(new_val) >= len(old_val) else old_val


def _merge_list(old_val: list, new_val: list) -> list:
    """合并列表字段：去重并集。"""
    seen = set()
    result = []
    for item in (new_val or []) + (old_val or []):
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _merge_entity_fields(existing: dict, incoming: dict) -> dict:
    """合并两个实体的 args 字段。字符串取更长的，列表去重合并。"""
    merged = dict(existing)
    str_fields_map = {
        "character": ["description", "role"],
        "location": ["description", "atmosphere"],
        "faction": ["summary", "org_type", "importance"],
    }
    list_fields_map = {
        "character": ["traits", "goals"],
        "location": ["features"],
        "faction": ["mandate_objectives", "influence_domains", "assets_resources", "methods_tactics", "tags"],
    }
    etype = existing.get("type", "")
    for f in str_fields_map.get(etype, []):
        merged[f] = _merge_str(existing.get(f, ""), incoming.get(f, ""))
    for f in list_fields_map.get(etype, []):
        merged[f] = _merge_list(existing.get(f, []) or [], incoming.get(f, []) or [])

    # 特殊处理：name 取 incoming（最新的）
    merged["name"] = incoming.get("name", existing.get("name", ""))

    return merged


def _find_existing_by_name(memory, etype: str, name: str) -> str | None:
    """在已有实体中按名称查找匹配项，返回实体 ID 或 None。"""
    n = _norm(name)
    if not n:
        return None

    if etype == "character":
        for cid in memory.list_characters():
            c = memory.load_character(cid)
            if c:
                full = _norm(c.full_name or "")
                first = _norm(c.first_name or "")
                if full and (n == full or n in full or full in n or n == first):
                    return cid
    elif etype == "location":
        for lid in memory.list_locations():
            loc = memory.load_location(lid)
            if loc:
                ln = _norm(loc.name or "")
                if ln and (n == ln or n in ln or ln in n):
                    return lid
    elif etype == "faction":
        for fid in memory.list_factions():
            fac = memory.load_faction(fid)
            if fac:
                fn = _norm(fac.name or "")
                if fn and (n == fn or n in fn or fn in n):
                    return fid
    return None


def _batch_dedup_entities(entities: list) -> list:
    """批内去重：同一批次内同名实体合并为一条。保留最后出现的版本作为基础。"""
    groups: dict[str, dict] = {}  # norm_name -> merged_entity
    order: list[str] = []  # 保持首次出现顺序

    for e in entities:
        name = (e.get("args", {}) or {}).get("name", "")
        key = _norm(name)
        if not key:
            order.append("__anon__" + str(len(order)))
            groups[order[-1]] = {"type": e["type"], "args": dict(e.get("args", {}))}
            continue
        if key in groups:
            # 合并：用新的覆盖、合并旧的
            groups[key]["args"] = _merge_entity_fields(groups[key]["args"], e.get("args", {}))
        else:
            order.append(key)
            groups[key] = {"type": e["type"], "args": dict(e.get("args", {}))}

    return [groups[k] for k in order]


@router.post("/project/{project_id}/import")
def import_settings(project_id: str, req: ImportRequest = Body(...)):
    """导入设定——preview 模式返回识别结果，confirm 模式执行导入（含智能去重合并）。"""
    project_dir = resolve_project(project_id)
    memory = MemoryManager(project_dir)

    # === Preview 模式：仅解析，不导入 ===
    if not req.confirm:
        if not req.content.strip():
            raise HTTPException(status_code=400, detail="内容为空")
        if len(req.content) > 50000:
            raise HTTPException(status_code=400, detail="内容过长（最多50000字符）")
        try:
            entities = _parse_document(req.content)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"LLM 解析失败: {e}")
        # 预览时也显示去重合并后的结果
        deduped = _batch_dedup_entities(entities)
        # 标记哪些已有磁盘实体
        for e in deduped:
            name = (e.get("args", {}) or {}).get("name", "")
            existing_id = _find_existing_by_name(memory, e["type"], name)
            e["_existing_id"] = existing_id or ""
            e["_action"] = "merge" if existing_id else "create"
        return {"preview": True, "entities": deduped, "original_count": len(entities), "deduped_count": len(deduped)}

    # === Confirm 模式：执行导入（含去重+合并） ===
    if not req.entities:
        return {"imported": [], "message": "没有要导入的实体"}

    # Layer 1: 批内去重
    entities = _batch_dedup_entities(req.entities)

    imported = []
    merged = []
    skipped = 0

    from ...memory.vector_store import VectorStore
    vs = VectorStore(project_dir)

    for e in entities:
        etype = e.get("type", "")
        args = dict(e.get("args", {}))
        name = args.get("name", "")

        # Layer 2: 查找磁盘已有实体
        existing_id = _find_existing_by_name(memory, etype, name)

        if existing_id:
            # 合并到已有实体
            if etype == "character":
                c = memory.load_character(existing_id)
                if c:
                    changed = False
                    new_desc = _merge_str(c.description or "", args.get("description", ""))
                    new_role = _merge_str(c.role or "", args.get("role", ""))
                    if new_desc != (c.description or ""):
                        c.description = new_desc; changed = True
                    if new_role != (c.role or ""):
                        c.role = new_role; changed = True
                    new_traits = _merge_list(getattr(c.personality, "core_traits", []) or [], args.get("traits", []))
                    if new_traits != (getattr(c.personality, "core_traits", []) or []):
                        c.personality.core_traits = new_traits; changed = True
                    new_goals = _merge_list(c.current_state.goals or [], args.get("goals", []))
                    if new_goals != (c.current_state.goals or []):
                        c.current_state.goals = new_goals; changed = True
                    if changed:
                        memory.save_character(c)
                        vs.index_character(c)
                    merged.append({"tool": "character.generate", "id": existing_id, "name": c.full_name, "action": "merged"})
                    continue
            elif etype == "location":
                loc = memory.load_location(existing_id)
                if loc:
                    changed = False
                    new_desc = _merge_str(loc.description or "", args.get("description", ""))
                    new_atmo = _merge_str(loc.atmosphere or "", args.get("atmosphere", ""))
                    if new_desc != (loc.description or ""):
                        loc.description = new_desc; changed = True
                    if new_atmo != (loc.atmosphere or ""):
                        loc.atmosphere = new_atmo; changed = True
                    new_feat = _merge_list(loc.features or [], args.get("features", []))
                    if new_feat != (loc.features or []):
                        loc.features = new_feat; changed = True
                    if changed:
                        memory.save_location(loc)
                        vs.index_location(loc)
                    merged.append({"tool": "location.generate", "id": existing_id, "name": loc.name, "action": "merged"})
                    continue
            elif etype == "faction":
                fac = memory.load_faction(existing_id)
                if fac:
                    changed = False
                    new_summary = _merge_str(fac.summary or "", args.get("summary", ""))
                    new_org = _merge_str(fac.org_type or "", args.get("org_type", ""))
                    if new_summary != (fac.summary or ""):
                        fac.summary = new_summary; changed = True
                    if new_org != (fac.org_type or ""):
                        fac.org_type = new_org; changed = True
                    if changed:
                        memory.save_faction(fac)
                        vs.index_faction(fac)
                    merged.append({"tool": "faction.generate", "id": existing_id, "name": fac.name, "action": "merged"})
                    continue

        # 全新创建
        from ...agent.runtime import PlanExecutor
        from ...tools.memory_tools import CharacterGenerateTool, LocationGenerateTool, FactionGenerateTool
        tool_map = {"character": "character.generate", "location": "location.generate", "faction": "faction.generate"}
        tool_name = tool_map.get(etype)
        if not tool_name:
            skipped += 1
            continue

        executor = PlanExecutor(ToolRegistry(), memory, vs)
        cls_map = {"character.generate": CharacterGenerateTool, "location.generate": LocationGenerateTool, "faction.generate": FactionGenerateTool}
        executor.tools.register(cls_map[tool_name](memory, vs))

        result = executor.execute_plan({"actions": [{"tool": tool_name, "args": args}]}, tick=0)
        for r in result.get("actions_executed", []):
            if r.get("success") and r.get("result", {}).get("success"):
                res = r["result"]
                imported.append({
                    "tool": r["tool"],
                    "id": res.get("character_id") or res.get("location_id") or res.get("faction_id") or "",
                    "name": res.get("name", ""),
                    "action": "created",
                })

    summary = f"新建 {len(imported)} 个, 合并更新 {len(merged)} 个"
    if skipped:
        summary += f", 跳过 {skipped} 个"
    logger.info("导入设定: %s", summary)
    return {"preview": False, "imported": imported, "merged": merged, "total": len(entities), "message": summary}
