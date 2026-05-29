"""Story thread lifecycle manager — auditing, aging, enforcement."""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from ..configs.constants import (
    THREAD_AUDIT_INTERVAL,
    THREAD_STALE_WARN,
    THREAD_STALE_FORCE,
)
from .entities import StoryThread

logger = logging.getLogger(__name__)

_AUDIT_SYSTEM_PROMPT = """你是故事结构分析师。请阅读以下场景摘要，识别当前已自然形成的叙事支线。

识别标准：
- 一条支线是一组彼此关联的事件/角色/冲突，跨越至少 2 个场景
- 支线有独立的发展方向——它在"朝某个目标推进"
- 支线中至少涉及 1 个具体角色
- 不要识别主角主线成长本身——只识别分支故事

对每条支线输出：名称、一句话描述、分类、重要度、涉及角色 ID、涉及场景 ID、
识别依据（从哪些场景看出的）、置信度（high/medium/low）。

只输出 JSON，不要其他文字。"""

_AUDIT_USER_TEMPLATE = """## 故事名
{novel_name}

## 最近场景
{recent_scenes}

## 已有支线（避免重复）
{existing_threads}

请识别最多 3 条新支线。按以下 JSON 格式输出：
{{"suggestions": [
  {{"name": "支线名称",
   "description": "一两句话描述",
   "category": "subplot|relationship|mystery|character_arc",
   "importance": "critical|high|medium|low",
   "related_characters": ["C001"],
   "related_scenes": ["S005", "S012"],
   "evidence": "从哪些场景识别出此支线",
   "confidence": "high|medium|low"}}
]}}
只输出 JSON。"""


class ThreadManager:
    """Manages story thread lifecycle across the emergent narrative."""

    def __init__(self, memory_manager, llm_interface=None, config=None):
        self.memory = memory_manager
        self.llm = llm_interface
        self.config = config or {}

    # ---- 查询 ----

    def get_active(self):
        return self.memory.get_threads_by_status("active")

    def get_pending(self):
        return self.memory.get_threads_by_status("pending")

    def get_stale(self, current_tick: int):
        """Return active threads sorted by stall count (desc)."""
        active = self.get_active()
        result = []
        for t in active:
            stall = current_tick - max(t.last_advanced_tick, t.introduced_tick)
            if stall >= THREAD_STALE_WARN:
                result.append((stall, t))
        result.sort(key=lambda x: -x[0])
        return [t for _, t in result]

    def get_all(self):
        return self.memory.get_all_threads()

    # ---- CRUD ----

    def create_thread(self, data: dict) -> StoryThread:
        tid = self.memory.generate_id("story_thread")
        thread = StoryThread(id=tid, **{k: v for k, v in data.items()
                              if k in StoryThread.__dataclass_fields__})
        thread.introduced_tick = data.get("introduced_tick", 0)
        thread.last_advanced_tick = data.get("last_advanced_tick", thread.introduced_tick)
        self.memory.save_thread(thread)
        logger.info("创建支线 %s: %s", tid, thread.name)
        return thread

    def update_thread(self, thread_id: str, data: dict) -> Optional[StoryThread]:
        thread = self.memory.load_thread(thread_id)
        if not thread:
            return None
        for key, value in data.items():
            if hasattr(thread, key):
                setattr(thread, key, value)
        self.memory.save_thread(thread)
        return thread

    def delete_thread(self, thread_id: str):
        self.memory.delete_thread(thread_id)

    def confirm_thread(self, thread_id: str) -> Optional[StoryThread]:
        """Pending → active."""
        return self.update_thread(thread_id, {"status": "active"})

    def reject_thread(self, thread_id: str) -> Optional[StoryThread]:
        """Pending → rejected."""
        return self.update_thread(thread_id, {"status": "rejected"})

    def advance_thread(self, thread_id: str, tick: int, scene_id: str, note: str = ""):
        self.memory.advance_thread(thread_id, tick, scene_id, note)

    # ---- LLM 审计 ----

    def run_audit(self, current_tick: int, novel_name: str = "") -> list[StoryThread]:
        """Run LLM audit to discover new threads. Returns pending suggestions."""
        if not self.llm:
            logger.warning("没有 LLM 接口，跳过支线审计")
            return []

        prompt = self._build_audit_prompt(current_tick, novel_name)
        try:
            response = self.llm.generate(prompt, max_tokens=800)
            data = self._parse_audit_response(response)
        except Exception as exc:
            logger.warning("支线审计 LLM 调用失败: %s", exc)
            return []

        suggestions = data.get("suggestions", [])
        if not suggestions:
            return []

        created = []
        existing_names = {t.name for t in self.get_all()}
        for s in suggestions:
            name = s.get("name", "").strip()
            if not name or name in existing_names:
                continue
            thread = self.create_thread({
                "name": name,
                "description": s.get("description", ""),
                "category": s.get("category", "subplot"),
                "importance": s.get("importance", "medium"),
                "source": "llm_suggested",
                "status": "pending",
                "introduced_tick": current_tick,
                "last_advanced_tick": current_tick,
                "related_characters": s.get("related_characters", []),
                "related_scenes": s.get("related_scenes", []),
                "suggestion_evidence": s.get("evidence", ""),
                "suggestion_confidence": s.get("confidence", "medium"),
            })
            created.append(thread)
            existing_names.add(name)

        if created:
            logger.info("LLM 审计发现 %d 条新支线建议", len(created))
        return created

    def _build_audit_prompt(self, current_tick: int, novel_name: str) -> str:
        scene_ids = self.memory.list_scenes()
        scene_summaries = []
        for sid in scene_ids[-10:]:
            scene = self.memory.load_scene(sid)
            if scene and scene.summary:
                summary = "; ".join(scene.summary) if isinstance(scene.summary, list) else scene.summary
                scene_summaries.append(f"S{scene.tick:03d}: {summary}")

        existing = self.get_all()
        existing_lines = []
        for t in existing:
            existing_lines.append(f"- {t.id} {t.name} [{t.status}] {t.description}")

        return _AUDIT_USER_TEMPLATE.format(
            novel_name=novel_name or "未知",
            recent_scenes="\n".join(scene_summaries) if scene_summaries else "暂无场景",
            existing_threads="\n".join(existing_lines) if existing_lines else "暂无已有支线",
        )

    @staticmethod
    def _parse_audit_response(response: str) -> dict:
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        return {}

    # ---- 看板格式化 ----

    def format_dashboard(self, current_tick: int) -> str:
        """生成支线看板——注入 planner context。"""
        active = self.get_active()
        if not active:
            return "暂无活跃支线。"

        stall_data = []
        forced = []
        for t in active:
            stall = current_tick - max(t.last_advanced_tick, t.introduced_tick)
            stall_data.append((stall, t))
            if stall >= self._force_threshold():
                forced.append(t)

        stall_data.sort(key=lambda x: -x[0])

        lines = ["### 故事支线看板", ""]
        for stall, t in stall_data:
            if stall >= self._force_threshold():
                tag = "█ 必须推进"
            elif stall >= self._warn_threshold():
                tag = "▄ 需推进"
            else:
                tag = "▂ 正常"

            chars = ", ".join(t.related_characters[:3]) if t.related_characters else "无"
            lines.append(f"- **{t.id} {t.name}** | {t.category} | 停滞{stall}章 | {tag}")
            lines.append(f"  角色: {chars} | 描述: {t.description}")
            lines.append("")

        if forced:
            lines.append("### 叙事债务·必须在本章推进")
            lines.append("")
            lines.append("以下支线已停滞超过 {} 章。本章计划必须至少推进其中 1 条，".format(self._force_threshold()))
            lines.append("否则计划将被拒绝。")
            lines.append("")
            for t in forced:
                stall = current_tick - max(t.last_advanced_tick, t.introduced_tick)
                lines.append(f"- **{t.id} {t.name}** — 停滞 {stall} 章。{t.description}")

        return "\n".join(lines)

    def format_stale_enforcement(self, current_tick: int) -> str:
        """如果有强制推进的支线，返回强制执行段落，否则空字符串。"""
        forced = [t for t in self.get_active()
                  if current_tick - max(t.last_advanced_tick, t.introduced_tick) >= self._force_threshold()]
        if not forced:
            return ""
        ids = ", ".join(t.id for t in forced)
        return (
            f"\n\n**支线强制推进：** 支线 {ids} 已停滞超过最大容忍章数。"
            f"你必须在 threads_addressed 字段中列出要推进的支线 ID。"
            f"如果 threads_addressed 为空，计划将被拒绝。"
        )

    def get_forced_ids(self, current_tick: int) -> list[str]:
        """返回必须推进的支线 ID 列表。"""
        return [t.id for t in self.get_active()
                if current_tick - max(t.last_advanced_tick, t.introduced_tick) >= self._force_threshold()]

    def _warn_threshold(self) -> int:
        return self.config.get("thread_audit.stale_warn", THREAD_STALE_WARN)

    def _force_threshold(self) -> int:
        return self.config.get("thread_audit.stale_force", THREAD_STALE_FORCE)
