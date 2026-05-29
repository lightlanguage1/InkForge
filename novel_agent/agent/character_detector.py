"""Character detection — LLM 驱动的角色名识别，零硬编码。"""

import json
import logging
import re
from typing import List, Set

logger = logging.getLogger(__name__)

_DETECT_PROMPT = """以下是一段小说场景文本。请识别其中出现的、有名字的角色。

已有的角色名单（不要重复报告这些）：
{existing_names}

请找出文本中出现的**新角色**——已有名单之外的、有具体姓名的角色。注意：
- 不包括无名的路人（如"一个老人""守卫"等没有具体姓名的描述）
- 不包括只在对话中被提及但未实际出场的角色
- 不包括角色内心回忆中的人物（除非他们确实在本场景中行动）

只返回 JSON：
{{"new_characters": [{{"name": "角色全名", "role": "在此场景中的角色定位"}}]}}
如果没有新角色，返回 {{"new_characters": []}}。"""


class CharacterDetector:
    """基于 LLM 的新角色检测，配合已有角色名库做快速确认。"""

    def __init__(self, memory_manager, config: dict = None, llm=None):
        self.memory = memory_manager
        self.config = config or {}
        self.llm = llm

    def get_existing_character_names(self) -> Set[str]:
        """从 memory 中获取所有已有角色名。"""
        names = set()
        for cid in self.memory.list_characters():
            char = self.memory.load_character(cid)
            if not char:
                continue
            family = char.family_name or ""
            given = char.first_name or ""
            if family and given:
                names.add(family + given)
            if given:
                names.add(given)
            for nick in (char.nicknames or []):
                if nick:
                    names.add(nick)
        return names

    def find_new_characters(self, scene_text: str) -> List[str]:
        """找出文本中出现但尚未注册的新角色名。

        优先使用 LLM 检测；若 LLM 不可用，回退到已有角色名库匹配。
        """
        existing = self.get_existing_character_names()

        if self.llm:
            return self._llm_detect(scene_text, existing)

        # 回退：用已有角色名在文本中做快速匹配（数据驱动，零硬编码）
        found = []
        for name in existing:
            if len(name) >= 2 and name in scene_text:
                found.append(name)
        return found

    def _llm_detect(self, scene_text: str, existing: Set[str]) -> List[str]:
        prompt = _DETECT_PROMPT.format(
            existing_names=", ".join(sorted(existing)) if existing else "暂无已有角色",
        )
        full_prompt = prompt + "\n\n场景文本：\n" + scene_text[:4000]
        try:
            response = self.llm.generate(full_prompt, max_tokens=300)
            data = self._parse_json(response)
            return [item["name"] for item in data.get("new_characters", []) if item.get("name")]
        except Exception as e:
            logger.warning("LLM 角色检测失败: %s", e)
            return []

    @staticmethod
    def _parse_json(response: str) -> dict:
        match = re.search(r'\{[\s\S]*\}', response)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {}

    def create_character_stub(self, name: str, role: str = "minor") -> str:
        """为新角色创建实体。中文字符自动拆分为姓+名。"""
        if len(name) >= 2 and all('一' <= c <= '鿿' for c in name[:2]):
            family_name = name[0]
            first_name = name[1:]
        else:
            family_name = ""
            first_name = name

        char_id = self.memory.generate_id("character")
        from ..memory.entities import Character

        character = Character(
            id=char_id,
            first_name=first_name,
            family_name=family_name,
            role=role,
            description=f"从场景文本中自动检测的角色。待补充详情。",
        )
        self.memory.save_character(character)
        return char_id
