"""场景后处理：事实提取 → 实体更新 → 世界观 → 角色检测。

将 agent/ 下的 5 个独立组件合并到此模块。减少类层次，保留核心逻辑。
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def update_from_scene(
    scene_text: str,
    scene_id: str,
    tick: int,
    state: dict,
    memory,
    llm,
    config: dict,
):
    """场景提交后的全部内存更新。依次执行。

    1. 事实提取 + 实体更新
    2. 世界观提取
    3. 角色检测
    """
    _extract_and_update(scene_text, scene_id, tick, state, memory, llm, config)
    _extract_lore(scene_text, scene_id, tick, memory, llm, config)
    _detect_characters(scene_text, memory, config)


def _extract_and_update(scene_text, scene_id, tick, state, memory, llm, config):
    """提取事实并更新实体。"""
    if not config.get('generation.enable_fact_extraction', True):
        return

    from ..agent.fact_extractor import FactExtractor
    from ..agent.entity_updater import EntityUpdater

    extractor = FactExtractor(llm, memory, config)
    updater = EntityUpdater(memory, config)

    try:
        facts = extractor.extract_facts(scene_text, {"scene_id": scene_id, "tick": tick})
        if facts:
            updater.apply_updates(facts, tick, scene_id, state)
    except (ValueError, json.JSONDecodeError, RuntimeError) as e:
        logger.warning("事实提取失败 (tick %d): %s", tick, e)


def _extract_lore(scene_text, scene_id, tick, memory, llm, config):
    """提取世界观规则并保存。"""
    if not config.get('generation.enable_lore_tracking', True):
        return

    from ..agent.lore_extractor import LoreExtractor
    from ..agent.lore_contradiction_detector import LoreContradictionDetector
    from ..memory.entities import Lore
    from ..memory.vector_store import VectorStore

    vector = VectorStore(memory.project_path)
    extractor = LoreExtractor(llm, memory, config)
    detector = LoreContradictionDetector(memory, vector, config)

    try:
        items = extractor.extract_lore(scene_text, {"scene_id": scene_id, "tick": tick}, tick)
    except (ValueError, json.JSONDecodeError, RuntimeError) as e:
        logger.warning("世界观提取失败 (tick %d): %s", tick, e)
        return

    for item in items:
        try:
            lore = Lore(
                id=memory.generate_lore_id(),
                lore_type=item.get('type', 'fact'),
                content=item.get('content', ''),
                category=item.get('category', 'other'),
                source_scene_id=scene_id,
                tick=tick,
                importance=item.get('importance', 'normal'),
                tags=item.get('tags', [])
            )
            memory.save_lore(lore)
            vector.index_lore(lore)
            detector.update_contradictions(lore.id)
        except (IOError, OSError, ValueError) as e:
            logger.warning("保存 lore 失败: %s", e)


def _detect_characters(scene_text, memory, config):
    """从场景文本中发现新角色名。"""
    if not config.get('generation.auto_detect_characters', True):
        return

    from ..agent.character_detector import CharacterDetector

    detector = CharacterDetector(memory, config)

    try:
        new_names = detector.find_new_characters(scene_text)
        if new_names and config.get('generation.auto_create_minor_characters', False):
            for name in new_names:
                detector.create_character_stub(name)
    except Exception as e:
        logger.warning("角色检测失败: %s", e)
