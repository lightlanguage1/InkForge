"""Skill injector - inject skill features into writer/planner context."""

import json
from pathlib import Path
from typing import List, Optional
from .models import Skill


def build_skill_context(state: dict, store_path: Optional[str] = None) -> str:
    """Build skill reference text for prompts.

    Loads full skill data from SKILL.yaml via SkillStore (using skill ID stored
    in state). Falls back to legacy inline data if store_path is not provided
    and state still contains the old embedded format.
    """
    active_skills = state.get("active_skills", [])
    if not active_skills:
        return ""

    # Load full skill objects from store when store_path is available
    skill_objects: List[dict] = []
    if store_path:
        from .store import SkillStore
        store = SkillStore({"skill": {"store_path": store_path}})
        for ref in active_skills:
            skill_id = ref.get("id", "")
            skill = store.load_skill(skill_id) if skill_id else None
            if skill:
                skill_objects.append({
                    "name": skill.name,
                    "mode": ref.get("mode", "reference"),
                    "style": skill.style_profile.__dict__ if skill.style_profile else {},
                    "patterns": [p.__dict__ for p in skill.patterns],
                })
            else:
                # Skill not found in store — skip silently
                pass
    else:
        # Legacy: state still has embedded data
        skill_objects = [
            s for s in active_skills
            if isinstance(s, dict) and s.get("style")
        ]

    if not skill_objects:
        return ""

    sections = []
    for skill in skill_objects:
        sections.append(f"## 风格参考: {skill['name']}")

        style = skill.get("style", {})
        if style:
            tags = style.get("style_tags", [])
            if tags:
                sections.append(f"标签: {', '.join(tags)}")
            sections.append(f"均句长: {style.get('avg_sentence_length', 'N/A')}字 (波动: {style.get('sentence_length_std', 'N/A')})")
            sections.append(f"对话占比: {style.get('dialogue_ratio', 'N/A')}")
            para = style.get("paragraph_length_avg")
            if para and para > 0:
                sections.append(f"均段长: {round(para)}字")

        patterns = skill.get("patterns", [])
        if patterns and skill.get("mode") in ("reference", "full"):
            sections.append("\n叙事技法:")
            for p in patterns[:5]:
                tpl = p.get("template", "")
                freq = p.get("frequency", 0)
                # 不注入 example —— example 含原著人物和情节，会污染写作上下文；
                # 只注入抽象结构模板，让 LLM 习得技法而非复制内容。
                sections.append(f"- [{p['type']}] {tpl}  (出现频率:{freq:.0%})")

        sections.append("")

    return "\n".join(sections)


class SkillInjector:
    """Inject skills into a project's writing context.

    Three modes:
    - "reference": inject as reference only (prompt guidance)
    - "style_only": only style profile
    - "full": all patterns (use with caution)
    """

    def __init__(self, project_path: str, config: dict):
        self.project_path = Path(project_path)
        self.config = config

    def inject(self, skills: List[Skill], mode: str = "reference"):
        """Store skill references (id + name + mode only) in project state.

        Full skill data stays in SKILL.yaml as the single source of truth.
        """
        from ..utils.file_ops import write_json
        state_file = self.project_path / "state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))

        state["active_skills"] = [
            {"id": s.id, "name": s.name, "mode": mode}
            for s in skills
        ]

        write_json(str(state_file), state)

    def clear_skills(self):
        """清空项目的所有活跃技能。"""
        from ..utils.file_ops import write_json
        state_file = self.project_path / "state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state["active_skills"] = []
        write_json(str(state_file), state)

    def build_skill_context(self, state: dict) -> str:
        """Build skill reference text for prompts."""
        store_path = (self.config.get("skill") or {}).get("store_path")
        return build_skill_context(state, store_path=store_path)
