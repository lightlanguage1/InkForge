"""小说质量打分器 — LLM 多维度评分 + 修改建议。

用于"黄金三章"打磨闭环：评分不到阈值 → 带反馈重写 → 再评 → 循环。
"""

import json
import logging
import re
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


_SCORING_PROMPT = """你是资深文学编辑，请为以下小说场景打分。

== 评分维度（每项 0-100） ==

1. **文笔 (prose)**: 语言质感、句式变化、节奏控制、描写精度
2. **节奏 (pacing)**: 场景推进速度是否得当、信息密度是否合适
3. **对话 (dialogue)**: 对话是否推动剧情/揭示性格、是否符合角色身份
4. **人物 (character)**: 角色行为是否一致、性格是否立体、情感是否真实
5. **设定遵守 (lore_compliance)**: 是否严格遵守世界观规则和势力立场
6. **张力 (tension)**: 冲突/悬念/情感张力是否有效
7. **推进力 (progress)**: 场景是否真正改变了故事状态、推进了主线

== 评分标准 ==
- 95-100: 出版级——可直接发表
- 85-94: 优秀——有亮点，少数可改进处
- 70-84: 合格——能用但平庸
- 50-69: 需大改——有明显缺陷
- 0-49: 不合格——需重写

== 场景上下文 ==
小说：{novel_name} | 第 {tick} 幕
POV：{pov_name}
意图：{scene_intention}
关键变化预期：{key_change}

== 世界观约束（必须检查） ==
{world_rules}

== 场景正文 ==
```
{scene_text}
```

只输出 JSON（不要其他文字）：
{{
  "scores": {{
    "prose": 85,
    "pacing": 80,
    "dialogue": 90,
    "character": 88,
    "lore_compliance": 95,
    "tension": 82,
    "progress": 87
  }},
  "total": 86,
  "highlights": ["写得好的地方 1", "写得好的地方 2"],
  "issues": [
    {{"dimension": "pacing", "severity": "major", "description": "问题描述", "suggestion": "具体修改建议"}}
  ],
  "rewrite_instructions": "如果需要重写，一句话概括修改方向"
}}"""


class ScoringEvaluator:
    """LLM 文学质量打分器。

    独立于 pass/fail 的 SceneEvaluator——这个是质量评审，那个是合规评审。
    用于打磨循环：评分 < 阈值 → 带反馈重写 → 再评。
    """

    def __init__(self, llm, config: dict):
        from ..configs.constants import (
            QUALITY_THRESHOLD_EARLY, QUALITY_THRESHOLD_NORMAL,
            QUALITY_FIRST_N_TICKS, MAX_POLISH_ROUNDS,
        )
        self.llm = llm
        self.config = config
        gen = config.get("generation", {}) if isinstance(config, dict) else {}
        # 前三章阈值 95，之后 85
        self.quality_threshold_first_n = gen.get("quality_threshold_first_n", QUALITY_FIRST_N_TICKS)
        self.quality_threshold_early = gen.get("quality_threshold_early", QUALITY_THRESHOLD_EARLY)
        self.quality_threshold_normal = gen.get("quality_threshold_normal", QUALITY_THRESHOLD_NORMAL)
        # 最大打磨轮数
        self.max_polish_rounds = gen.get("max_polish_rounds", MAX_POLISH_ROUNDS)

    # ---- Public API ----

    def score_scene(
        self,
        scene_text: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """对场景打分，返回评分详情。"""
        tick = context.get("current_tick", 0)
        prompt = _SCORING_PROMPT.format(
            novel_name=context.get("novel_name", ""),
            tick=tick,
            pov_name=context.get("pov_character_name", "未知"),
            scene_intention=context.get("scene_intention", ""),
            key_change=context.get("key_change", ""),
            world_rules=context.get("world_rules", ""),
            scene_text=scene_text[:3000],  # 采样前3000字
        )

        try:
            response = self.llm.generate(prompt, max_tokens=600)
            data = self._parse_json(response)
            if data is None:
                return self._fallback_score()
            return data
        except Exception as e:
            logger.warning("质量打分失败: %s", e)
            return self._fallback_score()

    def get_threshold(self, tick: int) -> int:
        """获取当前 tick 的质量阈值。"""
        if tick < self.quality_threshold_first_n:
            return self.quality_threshold_early
        return self.quality_threshold_normal

    def is_quality_tick(self, tick: int) -> bool:
        """是否对此 tick 启用质量打磨。前N章强制，之后可选。"""
        if tick < self.quality_threshold_first_n:
            return True
        return self.config.get("generation", {}).get("quality_loop_all_ticks", False)

    def format_feedback(self, score_result: Dict[str, Any]) -> str:
        """将评分结果格式化为重写反馈（注入 Writer prompt）。"""
        if not score_result:
            return ""

        total = score_result.get("total", 0)
        issues = score_result.get("issues", [])
        instructions = score_result.get("rewrite_instructions", "")

        lines = [
            "## [质量打磨] 上一版评分未达标",
            f"总分: {total}/100（目标: {self.quality_threshold_early}）",
            "",
        ]

        if issues:
            lines.append("### 需要修改的问题")
            for issue in issues:
                dim = issue.get("dimension", "?")
                sev = issue.get("severity", "minor")
                desc = issue.get("description", "")
                sug = issue.get("suggestion", "")
                lines.append(f"- [{dim}] [{sev}] {desc}")
                if sug:
                    lines.append(f"  修改建议: {sug}")
            lines.append("")

        if instructions:
            lines.append(f"### 重写方向\n{instructions}")
            lines.append("")

        lines.append("请根据以上反馈重新撰写此场景，保持故事连贯性。")
        return "\n".join(lines)

    # ---- Internal ----

    @staticmethod
    def _parse_json(response: str) -> Optional[dict]:
        """从 LLM 响应中提取 JSON。"""
        match = re.search(r'\{[^{}]*"scores"[^{}]*\}', response, re.DOTALL)
        if not match:
            match = re.search(r'\{.*\}', response, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _fallback_score() -> Dict[str, Any]:
        """评分失败时的兜底——通过但标记为未知质量。"""
        return {
            "scores": {},
            "total": 80,
            "highlights": [],
            "issues": [],
            "rewrite_instructions": "",
            "_fallback": True,
        }
