"""Prompt templates for agent LLM interactions.

Large instruction templates are loaded from data/templates/*.md at import time.
System prompts and format functions remain in code.
"""

import os
from pathlib import Path
from functools import lru_cache

from ..configs.constants import DATA_TEMPLATES_DIR

# === System prompts (stable, stay in code) ===

SYSTEM_CORE = """你是一个涌现式叙事系统的小说写作助手。

核心规则：
1. 严格 POV：只从当前视角角色的感知出发写作
2. 展示而非告知——通过动作、对话和感官细节来呈现
3. 每一幕必须推进情节或角色发展
4. 与已建立的世界观和角色特质保持一致
5. 追踪开放的故事线索——解决一些，创造另一些"""

SYSTEM_PLANNER = SYSTEM_CORE + """

所有输出必须是符合计划 schema 的有效 JSON。"""

SYSTEM_WRITER = SYSTEM_CORE + """

只输出小说正文，不要任何元评论或说明文字。"""


def split_prompt(template: str, context: dict) -> dict:
    """将 prompt 拆为 system（稳定段）和 user（动态段）。

    返回 {"system": str, "user": str}，可用于 chat() 接口。
    非 Anthropic 后端自动拼回纯文本。
    """
    lines = template.split("\n")
    mid = len(lines) // 3
    system_text = "\n".join(lines[:mid])

    user_text = template
    for key, value in context.items():
        placeholder = "{" + key + "}"
        if placeholder in user_text:
            user_text = user_text.replace(placeholder, str(value))

    return {"system": system_text, "user": user_text}


# === Template loader ===

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / DATA_TEMPLATES_DIR


@lru_cache(maxsize=8)
def _load_template(name: str) -> str:
    """Load a prompt template from data/templates/{name}.md."""
    path = _TEMPLATE_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    return path.read_text(encoding="utf-8")


def _format(name: str, context: dict) -> str:
    """Load template and interpolate context variables."""
    template = _load_template(name)
    return template.format(**context)


# === Public format functions ===

def format_planner_prompt(context: dict) -> str:
    return _format("planner_prompt", context)


def format_writer_prompt(context: dict) -> str:
    return _format("writer_prompt", context)


def format_fact_extraction_prompt(context: dict) -> str:
    return _format("fact_extraction_prompt", context)


