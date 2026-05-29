"""Skill injector - inject skill features into writer/planner context."""

import json
from pathlib import Path
from typing import List, Optional
from .models import Skill


def build_skill_context(state: dict) -> str:
    """Build skill reference text for prompts from project state.

    Returns formatted text to be included in Writer/Planner prompts,
    or empty string if no active skills.
    """
    active_skills = state.get("active_skills", [])
    if not active_skills:
        return ""

    sections = []
    for skill in active_skills:
        sections.append(f"## 风格参考: {skill['name']}")

        style = skill.get("style", {})
        if style:
            tags = style.get("style_tags", [])
            if tags:
                sections.append(f"标签: {', '.join(tags)}")
            sections.append(f"均句长: {style.get('avg_sentence_length', 'N/A')}字 (波动: {style.get('sentence_length_std', 'N/A')})")
            sections.append(f"对话占比: {style.get('dialogue_ratio', 'N/A')}")
            para = style.get('paragraph_length_avg')
            if para and para > 0:
                sections.append(f"均段长: {round(para)}字")

        patterns = skill.get("patterns", [])
        if patterns and skill.get("mode") in ("reference", "full"):
            sections.append("\n写作模式:")
            for p in patterns[:5]:
                tpl = p.get('template', '')
                ex = p.get('example', '')
                freq = p.get('frequency', 0)
                sections.append(f"- [{p['type']}] {tpl}  (频率:{freq:.0%})")
                if ex:
                    sections.append(f"  例句: \"{ex}\"")

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
        """Inject skills into the project state."""
        from ..utils.file_ops import write_json
        state_file = self.project_path / "state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))

        state["active_skills"] = [
            {
                "id": s.id,
                "name": s.name,
                "mode": mode,
                "style": s.style_profile.__dict__ if s.style_profile else {},
                "patterns": [p.__dict__ for p in s.patterns],
                "archetypes": [a.__dict__ for a in s.character_archetypes],
            }
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
        return build_skill_context(state)
