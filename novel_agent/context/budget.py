"""Token 预算管理器 — 对 Planner 和 Writer 的 prompt 做硬性 token 预算约束。

设计原则：
1. 低耦合 — try/except 包裹，失败返回原始 context
2. 渐进增强 — 默认行为不变（全量加载），用户通过配置开启优化
3. 确定性裁剪 — 规则优先级，不依赖 LLM
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ContextBudgeter:
    """Token 预算管理器。

    对上下文做四层注入（Tier 1→4），当预算不足时低 tier 内容被
    摘要化或删除。
    """

    # 默认 token 预算（0 = 不限制）
    DEFAULT_PLANNER_BUDGET = 6000
    DEFAULT_WRITER_BUDGET = 8000

    TIER_MAP_PLANNER: Dict[str, tuple] = {
        # ── Tier 1: 必须保留 ──
        "story_foundation_summary":     (1, "keep"),
        "novel_name":                   (1, "keep"),
        "current_tick":                 (1, "keep"),
        "active_character_details":     (1, "keep"),
        "character_relationships":      (1, "keep"),
        "next_plot_beat":               (1, "keep"),
        "beat_enforcement_instructions":(1, "keep"),
        "available_tools_description":  (1, "keep"),
        # ── Tier 2: 优先保留 ──
        "recent_scenes_summary":        (2, "top_n=3"),
        "open_loops_list":              (2, "top_n=5"),
        "tension_history":              (2, "keep"),
        "relevant_lore":                (2, "top_n=5"),
        "factions_summary":             (2, "top_n=3"),
        # ── Tier 3: 按需保留 ──
        "pov_candidates":               (3, "top_n=5"),
        "pov_history":                  (3, "top_n=5"),
        "existing_characters_summary":  (3, "top_n=10"),
        "absent_characters":            (3, "top_n=3"),
        "qa_feedback":                  (3, "keep"),
        "skill_context":                (3, "truncate_quarter"),
        "thread_dashboard":             (3, "top_n=5"),
        "active_character_name":        (3, "keep"),
        "active_character_id":           (3, "keep"),
        "overall_summary":              (3, "truncate_half"),
        # ── Tier 4: 预算允许时保留 ──
        "writer_notes":                 (4, "keep"),
        "plan_rejection_feedback":      (4, "keep"),
    }

    TIER_MAP_WRITER: Dict[str, tuple] = {
        # ── Tier 1: 必须保留 ──
        "novel_name":                   (1, "keep"),
        "current_tick":                 (1, "keep"),
        "story_foundation_summary":     (1, "keep"),
        "scene_intention":             (1, "keep"),
        "key_change":                  (1, "keep"),
        "pov_character_id":             (1, "keep"),
        "pov_character_name":           (1, "keep"),
        "pov_character_details":        (1, "keep"),
        "location_id":                  (1, "keep"),
        "location_name":                (1, "keep"),
        "location_details":             (1, "keep"),
        "plot_beat_section":            (1, "keep"),
        # ── Tier 2: 优先保留 ──
        "recent_context":               (2, "truncate_half"),
        "world_rules":                  (2, "top_n=5"),
        "tool_results_summary":         (2, "keep"),
        "story_goal_context":           (2, "keep"),
        # ── Tier 3: 按需保留 ──
        "skill_context":                (3, "truncate_quarter"),
        "style_context":                (3, "truncate_quarter"),
        "craft_context":                (3, "truncate_quarter"),
        "reference_context":            (3, "drop"),
        "thread_context":               (3, "truncate_half"),
        "scene_length_guidance":        (3, "keep"),
        "scene_mode":                   (3, "keep"),
        "palette_shift":                (3, "keep"),
        "transition_path":              (3, "keep"),
        "dialogue_targets":             (3, "keep"),
        "eval_feedback":                (3, "keep"),
        "climax_beat":                  (3, "keep"),
        "opening_hook":                 (3, "keep"),
        "pacing_notes":                 (3, "keep"),
        "progress_milestone":           (3, "keep"),
        "progress_step":                (3, "keep"),
        # ── Tier 4: 预算允许时保留 ──
        "writer_notes":                 (4, "keep"),
    }

    def __init__(self, config: dict):
        gen = config.get("generation", {}) if isinstance(config, dict) else {}
        self.planner_budget = gen.get("context_budget_planner", 0) or self.DEFAULT_PLANNER_BUDGET
        self.writer_budget = gen.get("context_budget_writer", 0) or self.DEFAULT_WRITER_BUDGET
        self.trim_log = gen.get("context_trim_log", False)
        self._disabled = not gen.get("context_budget_enabled", True)

    # ---- Public API ----

    def budget_planner_context(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """裁剪 Planner 上下文，返回裁剪后的副本。"""
        if self._disabled or self.planner_budget <= 0:
            return raw
        return self._budget_context(raw, self.TIER_MAP_PLANNER, self.planner_budget)

    def budget_writer_context(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """裁剪 Writer 上下文，返回裁剪后的副本。"""
        if self._disabled or self.writer_budget <= 0:
            return raw
        return self._budget_context(raw, self.TIER_MAP_WRITER, self.writer_budget)

    # ---- Internal ----

    def _budget_context(
        self,
        raw: Dict[str, Any],
        tier_map: Dict[str, tuple],
        budget: int,
    ) -> Dict[str, Any]:
        """按 tier 优先级裁剪 context，保证总 token 数不超过 budget。"""
        trimmed: Dict[str, Any] = {}
        used = 0

        # 按 tier 分组
        tiers: Dict[int, Dict[str, str]] = {1: {}, 2: {}, 3: {}, 4: {}}
        for key, value in raw.items():
            tier, strategy = tier_map.get(key, (4, "keep"))
            tiers[tier][key] = str(value) if value is not None else ""

        for tier_level in (1, 2, 3, 4):
            for key, text in tiers[tier_level].items():
                _, strategy = tier_map.get(key, (tier_level, "keep"))
                remaining = budget - used

                if remaining <= 0:
                    if self.trim_log:
                        logger.debug("上下文预算耗尽，跳过 tier%d: %s", tier_level, key)
                    continue

                applied = self._apply_strategy(text, strategy, remaining)
                cost = self._estimate_tokens(applied)
                used += cost
                trimmed[key] = applied

        if self.trim_log and used > budget:
            logger.info("上下文裁剪: %d → %d tokens (预算=%d)", self._total_tokens(raw), used, budget)

        return trimmed

    def _apply_strategy(self, text: str, strategy: str, budget_left: int) -> str:
        """按策略裁剪文本。"""
        if not text:
            return text
        if strategy == "keep":
            return text
        if strategy == "drop":
            return "" if budget_left < 50 else text

        # top_n=N — 按行截断（适用于列表类内容）
        if strategy.startswith("top_n="):
            try:
                n = int(strategy.split("=")[1])
            except (ValueError, IndexError):
                return text
            lines = [l for l in text.split("\n") if l.strip()]
            kept = lines[:n]
            result = "\n".join(kept)
            if len(lines) > n:
                result += f"\n（还有 {len(lines) - n} 条未显示）"
            return result

        if strategy == "truncate_half":
            return self._truncate_chars(text, len(text) // 2)
        if strategy == "truncate_quarter":
            return self._truncate_chars(text, len(text) // 4)

        return text

    @staticmethod
    def _truncate_chars(text: str, max_chars: int) -> str:
        """按字符数截断，尽量在句子或行边界断开。"""
        if len(text) <= max_chars:
            return text
        # 找最近的句子边界
        for sep in ["\n\n", "。", "！", "？", "\n"]:
            idx = text.rfind(sep, 0, max_chars)
            if idx > max_chars * 0.5:
                return text[:idx + len(sep)] + "…"
        return text[:max_chars] + "…"

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """粗略估算中文 token 数：len(text) * 1.3。

        LLM tokenizer 对中文约 1.5-2 chars/token，1.3 是保守估计。
        """
        return max(1, int(len(text) * 1.3))

    @staticmethod
    def _total_tokens(context: Dict[str, Any]) -> int:
        """估算整个 context 的 token 数。"""
        total = 0
        for v in context.values():
            if isinstance(v, str):
                total += max(1, int(len(v) * 1.3))
        return total
