"""Scene evaluator — quality and consistency checks with LLM fallback."""

import json
import logging
import re
from typing import Dict, Any, List, Optional

from ..plot.manager import PlotOutlineManager

logger = logging.getLogger(__name__)

# ---- Fast-path keywords (bypass LLM when none are matched) ----------------

_FAST_PATH_MARKERS = [
    "他不知道的是", "殊不知", "后来他才知道",
    "谁也不曾料到", "没有人注意到", "他们不知道",
]

# ---- LLM judge prompts --------------------------------------------------

_POV_JUDGE_PROMPT = """你是小说POV检测专家。请通读以下场景，判断是否存在视点（POV）违规。

当前POV角色：{character_name}（角色类型：{role}）

POV规则：
- 一切描写必须通过 {character_name} 的感知过滤——他看到、听到、感受到、想到的
- 禁止揭示其他角色的内心想法（除非 {character_name} 能观察到其外部表现）
- 禁止叙述者直接介入评论（全知叙述）
- 禁止跳到另一个角色的视角（头跳）
- 禁止出现"{character_name}不知道的是"之类的全知预告

判断标准：
- 角色基于经验/观察做出的合理推测 → 不算违规
- 角色回忆过去的事 → 不算违规
- 角色猜测/想象别人的想法 → 不算违规（只要明确是他在想）
- 叙述者直接说出角色不可能知道的信息 → 违规
- 突然从另一个角色的感官出发描写 → 违规

场景全文：
```
{scene_text}
```

请找出所有POV违规之处。只输出JSON：
{{"violations": [{{"text": "违规原文片段", "reason": "为什么这是违规"}}], "passed": true/false}}"""

_CONTINUITY_JUDGE_PROMPT = """你是小说连续性检测专家。场景中POV角色的身体状况与行动存在矛盾。

POV角色：{character_name}
身体状态：{physical_state}
矛盾动作：{action}

场景文本片段：
```
{text_snippet}
```

请判断：角色的行动是否与其身体状况构成真正的连续性矛盾？
- 如果角色只是尝试做动作但失败了 → 不算矛盾
- 如果角色以受伤状态做出了不可能的动作 → 才是矛盾

只输出JSON：{{"is_contradiction": true/false, "reason": "一句话理由(中文)"}}"""


_LOGIC_QA_PROMPT = """你是小说逻辑审核专家。通读以下场景，找出其中的逻辑谬误和设定矛盾。

== 检测规则（通用，适用于所有题材） ==

1. **时间自洽性**：场景内的时间跨度是否与事件量匹配？描述的事件在所述时间段内能否完成？
   例：一句话"三天后"但中间没有任何过渡 → warning。但星际航行、修炼闭关等世界观允许的长时间跨度不算问题。

2. **因果关系**：事件之间是否有合理的因果链？是否存在"因为A所以B"但A和B之间逻辑断裂的情况？

3. **性格/关系一致性**：角色的行为和对话是否与前面已建立的性格/关系一致？如有显著变化，是否有充分的剧情铺垫？

4. **设定遵守**：场景中的事件是否违反了下方列出的世界观规则？如果世界观明确允许某设定，则不算违规。

5. **信息连续性**：前面场景中已确认的信息（角色位置、物品归属、已经发生的事件等）是否在本场景中被无故推翻或无视？

6. **能力一致性**：角色的能力/技能是否与之前的表现一致？没有铺垫的新能力/知识突然出现 → error。

== 不检测的内容 ==
- 如果世界观规则明确允许（如魔法世界可以飞行、科幻世界可以跃迁），不算违规
- 角色的主观感受、情感反应（这些是创作自由）
- 对话的措辞风格

== 场景上下文 ==
- 故事：{novel_name} | 类型由世界观决定
- 第 {current_tick} 幕
- POV：{pov_name}（{pov_age}岁）
- 意图：{scene_intention}
- 已确立的世界观（这些规则不可违反）：{lore_rules}

== 场景全文 ==
```
{scene_text}
```

只输出JSON：
{{"issues": [{{"type": "time|causality|character|setting|info|ability", "description": "具体问题（中文）", "severity": "error|warning"}}], "passed": true/false}}
无问题则 passed=true, issues=[]。只返回JSON。"""


class SceneEvaluator:
    """Evaluates scene quality and consistency.

    Uses fast keyword pre-filters for POV and continuity checks.
    When keywords trigger and an LLM interface is available, asks the
    LLM to confirm ambiguous cases — reducing false positives.
    """

    def __init__(self, memory_manager, config, llm_interface=None):
        self.memory = memory_manager
        self.config = config
        self.llm = llm_interface

    # ---- public API ------------------------------------------------------

    def evaluate_scene(self, scene_text: str, scene_context: Dict[str, Any]) -> Dict[str, Any]:
        issues: List[str] = []
        warnings: List[str] = []
        checks: Dict[str, bool] = {}

        checks["pov"] = self._check_pov(scene_text, scene_context)
        if not checks["pov"]:
            issues.append("POV违规：场景存在全知叙述或视角跳跃，需要修正")

        checks["continuity"] = self._check_continuity(scene_text, scene_context)
        if not checks["continuity"]:
            issues.append("连续性错误：场景与角色状态矛盾")

        # LLM 时间/逻辑一致性评审 — severity=error 会阻断场景，必须重写
        logic_result = self._check_logic(scene_text, scene_context)
        if logic_result:
            checks["logic"] = logic_result.get("passed", True)
            for issue in logic_result.get("issues", []):
                msg = f"[{issue.get('type', '?')}] {issue.get('description', '')}"
                if issue.get("severity") == "error":
                    issues.append(msg)
                else:
                    warnings.append(msg)

        continuity_flags: List[str] = []
        if not checks["continuity"]:
            continuity_flags.append("possible_continuity_issue")

        qa_metrics = self._compute_qa_metrics(scene_text, scene_context, continuity_flags, warnings)

        passed = all(checks.values()) and len(issues) == 0

        result: Dict[str, Any] = {
            "passed": passed,
            "issues": issues,
            "warnings": warnings,
            "checks": checks,
        }
        result.update(qa_metrics)
        return result

    # ---- POV check -------------------------------------------------------

    def _check_pov(self, text: str, context: Dict[str, Any]) -> bool:
        """POV check: fast-path keyword bypass → LLM full-scene scan."""
        # Run POV check via LLM whenever available
        text_lower = text.lower()
        if not any(m in text_lower for m in _FAST_PATH_MARKERS):
            if not self.llm:
                return True

        if self.llm:
            return self._llm_check_pov(text, context)
        return False

    def _llm_check_pov(self, text: str, context: Dict[str, Any]) -> bool:
        """LLM scans the full scene for any form of POV violation."""
        pov_id = context.get("pov_character_id", "")
        char_name = context.get("pov_character_name", "未知")
        char_role = ""
        if pov_id:
            char = self.memory.load_character(pov_id)
            if char:
                char_name = char.display_name or char_name
                char_role = char.role or ""

        # Send first 2500 chars to keep token cost low
        sample = text[:2500]

        prompt = _POV_JUDGE_PROMPT.format(
            character_name=char_name,
            role=char_role or "未知",
            scene_text=sample,
        )
        try:
            response = self.llm.generate(prompt, max_tokens=300)
            data = self._extract_json(response)
            if data is None:
                logger.warning("LLM POV check: JSON parse failed, defaulting to pass")
                return True
            violations = data.get("violations", [])
            passed = data.get("passed", True)
            if violations:
                for v in violations:
                    logger.info("POV违规: %s — %s", v.get("text", "")[:40], v.get("reason", ""))
            return passed
        except Exception:
            logger.warning("LLM POV check failed, defaulting to pass")
        return True

    # ---- continuity check ------------------------------------------------

    def _check_continuity(self, text: str, context: Dict[str, Any]) -> bool:
        """Two-phase continuity check: heuristic → LLM confirmation."""
        pov_id = context.get("pov_character_id")
        if not pov_id:
            return True
        character = self.memory.load_character(pov_id)
        if not character:
            return True

        text_lower = text.lower()
        physical_state = (character.current_state.physical_state or "").lower()

        if "injured" in physical_state or "wounded" in physical_state:
            athletic_actions = ["leaped", "sprinted", "跃起", "飞奔", "猛地起身", "一跃"]
            for action in athletic_actions:
                if action in text_lower or action in text:
                    if self.llm:
                        return self._llm_check_continuity(text, character, action, context)
                    return False
        return True

    def _llm_check_continuity(self, text: str, character, action: str, context: Dict[str, Any]) -> bool:
        char_name = character.display_name or character.first_name or "角色"
        hit_pos = text.find(action)
        start = max(0, hit_pos - 100)
        end = min(len(text), hit_pos + 100)
        snippet = text[start:end]

        prompt = _CONTINUITY_JUDGE_PROMPT.format(
            character_name=char_name,
            physical_state=character.current_state.physical_state or "受伤",
            action=action,
            text_snippet=snippet,
        )
        try:
            response = self.llm.generate(prompt, max_tokens=150)
            data = self._extract_json(response)
            if data and not data.get("is_contradiction", True):
                logger.info("LLM continuity check: false alarm — %s", data.get("reason", ""))
                return True
            logger.info("LLM continuity check: confirmed — %s", data.get("reason", "") if data else "parse failed")
        except Exception:
            logger.warning("LLM continuity check failed, falling back to keyword result")
        return False

    # ---- logic QA (LLM 时间/年龄/逻辑一致性评审) --------------------------

    def _check_logic(self, text: str, context: Dict[str, Any]) -> dict | None:
        """LLM 评审场景的时间连续性、年龄一致性和逻辑矛盾。

        总是调用 LLM（不像 POV 有快速路径），因为逻辑评审需要理解
        故事上下文，无法用关键词判断。
        """
        if not self.llm:
            return None

        tick = context.get("current_tick", 0)
        # Run logic QA every tick — the cost of missing contradictions far outweighs LLM cost
        if tick > 0:
            pass

        pov_id = context.get("pov_character_id", "")
        char_name = context.get("pov_character_name", "未知")
        char_age = ""
        if pov_id:
            char = self.memory.load_character(pov_id)
            if char:
                char_name = char.display_name or char_name
                char_age = str(char.physical_traits.age) if char.physical_traits and char.physical_traits.age else "未知"

        # 收集世界观规则 — more context for better consistency checks
        lore_items = self.memory.load_all_lore()
        critical = [l for l in lore_items if getattr(l, "importance", "") == "critical"]
        important = [l for l in lore_items if getattr(l, "importance", "") == "important"]
        normal = [l for l in lore_items if getattr(l, "importance", "") not in ("critical", "important")]
        selected = critical + important[-5:] + normal[-5:]
        lore_text = "; ".join(f"[{getattr(l, 'importance', '?')}] {l.content[:100]}" for l in selected[-15:]) if selected else "暂无"

        prompt = _LOGIC_QA_PROMPT.format(
            novel_name=context.get("novel_name", ""),
            current_tick=context.get("current_tick", 0),
            pov_name=char_name,
            pov_age=char_age,
            scene_intention=context.get("scene_intention", ""),
            lore_rules=lore_text,
            scene_text=text[:3000],
        )

        try:
            response = self.llm.generate(prompt, max_tokens=400)
            data = self._extract_json(response)
            if data is None:
                return None
            return data
        except Exception:
            return None

    # ---- JSON extraction -------------------------------------------------

    @staticmethod
    def _extract_json(response: str) -> Optional[dict]:
        match = re.search(r'\{[^{}]*\}', response)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None

    # ---- QA metrics (non-fatal quality signals) --------------------------

    def _compute_qa_metrics(
        self,
        text: str,
        context: Dict[str, Any],
        continuity_flags: List[str],
        warnings: List[str],
    ) -> Dict[str, Any]:
        key_change = context.get("key_change", "") or ""
        progress_milestone = context.get("progress_milestone", "") or ""
        scene_mode = context.get("scene_mode", "") or ""
        dialogue_targets_raw = context.get("dialogue_targets", "") or ""

        text_lower = text.lower()

        def extract_keywords(value: str) -> List[str]:
            """Extract meaningful substrings from a Chinese sentence.

            Chinese has no spaces — split by common punctuation and
            take chunks of 2+ characters.
            """
            import re
            chunks = re.split(r'[，。、；：！？\s,.;:!?\-\—]+', value)
            result = []
            for chunk in chunks:
                chunk = chunk.strip()
                if len(chunk) >= 2:
                    result.append(chunk)
                # Also take character bigrams for broader matching
                for i in range(len(chunk) - 1):
                    result.append(chunk[i:i+2])
            return list(set(result))

        change_keywords = extract_keywords(key_change) or extract_keywords(progress_milestone)
        # A change is "achieved" if at least 30% of the key_change keywords
        # appear in the scene text (fuzzy, not exact substring)
        kw_hits = 0
        if change_keywords:
            kw_hits = sum(1 for w in change_keywords if w in text_lower)
            achieved_change_value = kw_hits >= max(1, len(change_keywords) * 0.3)
        else:
            achieved_change_value = True

        achieved_change = {
            "value": achieved_change_value,
            "explanation": f"{kw_hits}/{len(change_keywords)} keywords matched" if change_keywords else "no keywords to match",
        }

        # Count Chinese dialogue pairs: 「」, "", '', ""
        quote_pairs = (
            len(re.findall(r'「[^」]*」', text)) +
            len(re.findall(r'"[^"]*"', text)) +
            len(re.findall(r'“[^”]*”', text)) +
            len(re.findall(r"'[^']*'", text))
        )
        dialogue_count = quote_pairs

        min_exchanges: Optional[int] = None
        met_dialogue_target: Optional[bool] = None
        if isinstance(dialogue_targets_raw, dict):
            min_exchanges = dialogue_targets_raw.get("min_exchanges")
        elif isinstance(dialogue_targets_raw, str):
            match = re.search(r"min_exchanges\s*[:=]\s*(\d+)", dialogue_targets_raw)
            if match:
                try:
                    min_exchanges = int(match.group(1))
                except ValueError:
                    min_exchanges = None
        if isinstance(min_exchanges, int):
            met_dialogue_target = dialogue_count >= min_exchanges

        transition_clarity_score = 8 if context.get("transition_path") else 5
        transition_notes = (
            "Transition path provided in plan."
            if context.get("transition_path")
            else "No explicit transition_path provided."
        )

        mode_used = scene_mode or "unknown"

        recent_qa: List[Dict[str, Any]] = []
        try:
            recent_qa = self.memory.get_recent_scene_qa(count=3)
        except Exception:
            pass

        recent_modes = []
        for entry in recent_qa:
            evaluation = entry.get("evaluation", {}) or {}
            m = evaluation.get("mode_used")
            if isinstance(m, str) and m:
                recent_modes.append(m)

        mode_diversity_warning = False
        if mode_used != "unknown" and recent_modes:
            last_modes = recent_modes[-3:]
            if len(last_modes) >= 2 and all(m == last_modes[-1] for m in last_modes) and mode_used == last_modes[-1]:
                mode_diversity_warning = True
            elif len(last_modes) >= 2 and all(m == mode_used for m in last_modes):
                mode_diversity_warning = True

        if mode_diversity_warning:
            if mode_used == "technical":
                warnings.append("最近几幕重复了技术性场景模式；下次可以考虑对话或政治场景以增加多样性。")
            else:
                warnings.append(f"最近几幕重复了 scene_mode '{mode_used}'；建议更换模式以增加多样性。")

        novelty_score = 5.0
        if recent_qa:
            last_eval = recent_qa[-1].get("evaluation", {}) or {}
            last_mode = last_eval.get("mode_used")
            last_achieved = (last_eval.get("achieved_change") or {}).get("value")
            last_dialogue = last_eval.get("dialogue_count")

            score = 5.0
            if mode_used != "unknown" and isinstance(last_mode, str) and last_mode:
                score += 1.5 if mode_used != last_mode else -1.0
            if isinstance(achieved_change_value, bool) and isinstance(last_achieved, bool):
                if achieved_change_value != last_achieved:
                    score += 0.5
            if isinstance(dialogue_count, int) and isinstance(last_dialogue, int):
                if dialogue_count == 0 and last_dialogue == 0:
                    score -= 1.0
                elif (dialogue_count == 0) != (last_dialogue == 0):
                    score += 1.0
                elif abs(dialogue_count - last_dialogue) <= 2:
                    score -= 0.5
            novelty_score = max(1.0, min(9.0, score))

        beat_hint_alignment: Dict[str, Any] = {"beat_id": None, "score": None, "label": "none"}
        try:
            manager = PlotOutlineManager(self.memory.project_path)
            next_beat = manager.get_next_beat()
        except Exception:
            next_beat = None

        if next_beat is not None:
            beat_id = getattr(next_beat, "id", None)
            description = getattr(next_beat, "description", "") or ""
            beat_hint_alignment["beat_id"] = beat_id
            beat_keywords = extract_keywords(description)
            if beat_keywords:
                unique_keywords = set(beat_keywords)
                shared = sum(1 for w in unique_keywords if w in text_lower)
                ratio = shared / max(1, len(unique_keywords))
                beat_hint_alignment["score"] = round(ratio, 2)
                if ratio >= 0.6:
                    beat_hint_alignment["label"] = "high"
                elif ratio >= 0.3:
                    beat_hint_alignment["label"] = "medium"
                elif ratio > 0:
                    beat_hint_alignment["label"] = "low"
                else:
                    beat_hint_alignment["label"] = "none"

        return {
            "achieved_change": achieved_change,
            "dialogue_count": dialogue_count,
            "dialogue_target": {"min_exchanges": min_exchanges, "met": met_dialogue_target},
            "transition_clarity": {"score": transition_clarity_score, "notes": transition_notes},
            "mode_used": scene_mode or "unknown",
            "mode_diversity_warning": mode_diversity_warning,
            "novelty_score": novelty_score,
            "continuity_flags": continuity_flags,
            "beat_hint_alignment": beat_hint_alignment,
        }
