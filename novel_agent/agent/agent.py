"""Main StoryAgent orchestrator for coordinating the planning and execution loop."""

import json
import logging
import re
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

from .context import ContextBuilder
from .prompts import format_planner_prompt, SYSTEM_PLANNER
from .schemas import validate_plan
from .runtime import PlanExecutor
from .plan_manager import PlanManager
from .writer_context import WriterContextBuilder
from .writer import SceneWriter
from .evaluator import SceneEvaluator
from .scene_committer import SceneCommitter
from .tension_evaluator import TensionEvaluator
from .scorer import ScoringEvaluator
from ..tools.registry import ToolRegistry
from ..memory.manager import MemoryManager
from ..memory.vector_store import VectorStore
from ..memory.summarizer import SceneSummarizer
from ..configs.constants import (
    BEAT_LOW_CONFIDENCE_THRESHOLD,
    GOAL_PROMOTION_WINDOW_START,
    GOAL_PROMOTION_WINDOW_END,
    LOOP_MIN_MENTIONS_FOR_PROMOTION,
)
from ..plot.manager import PlotOutlineManager


def _format_eval_feedback(eval_result: dict) -> str:
    """Format evaluation issues as Chinese feedback for the Writer retry."""
    issues = eval_result.get("issues", [])
    warnings = eval_result.get("warnings", [])
    if not issues and not warnings:
        return ""
    lines = ["## [修正] 上一版场景存在问题，请修正：", ""]
    for i, issue in enumerate(issues, 1):
        lines.append(f"{i}. **{issue}**")
    if warnings:
        lines.append("")
        lines.append("**建议改进：**")
        for w in warnings:
            lines.append(f"- {w}")
    lines.append("")
    lines.append("请重新生成场景，务必修正上述问题。保持故事的连贯性和文笔质量。")
    return "\n".join(lines)


class StoryAgent:
    """Main agent orchestrator for story generation.

    Coordinates the tick cycle:
    1. Plan — gather context, generate plan, execute tools
    2. Write — build writer context, write scene prose
    3. Commit — evaluate, save tension, commit scene
    4. Update — extract facts, entities, lore, detect characters
    """
    
    def __init__(
        self,
        project_path: Path,
        llm_interface,
        tool_registry: ToolRegistry,
        config: dict,
        save_prompts: bool = False
    ):
        """Initialize story agent.
        
        Args:
            project_path: Path to novel project
            llm_interface: LLM interface (CodexInterface or similar)
            tool_registry: Registry of available tools
            config: Project configuration
            save_prompts: Whether to save prompts to files (Phase 7A.5)
        """
        self.project_path = Path(project_path)
        from ..tools.provider import LLMProvider
        from ..tools.router import ModelRouter

        self.tools = tool_registry
        self.config = config
        self._router = ModelRouter(config)

        # Dual-connection architecture:
        #   self.llm       → Writer + Planner (creative quality)
        #   self.agent_llm → Evaluator + Extractors (cost efficiency)
        #
        # When no separate extractor model is configured (empty or same as
        # main model), agent_llm reuses self.llm — both tasks share one
        # API connection.  When a different model is configured (e.g. a
        # local Ollama server) it is used for agent tasks; if that model
        # is unreachable the initialisation falls back to self.llm.
        backend_type = "anthropic" if "claude" in str(config.get("llm.model", "")).lower() else "api"
        self.llm = LLMProvider(llm_interface, backend_type)
        self.agent_llm = self._init_agent_llm(llm_interface, config, backend_type)

        # Initialize components
        self.memory = MemoryManager(self.project_path)
        self.vector = VectorStore(self.project_path)
        from ..memory.thread_manager import ThreadManager
        self.thread_manager = ThreadManager(self.memory, self.agent_llm, config)
        self.context_builder = ContextBuilder(
            self.memory, self.vector, self.tools, config,
        )
        self.executor = PlanExecutor(self.tools, self.memory, self.vector)
        self.plan_manager = PlanManager(self.project_path)

        # Phase 4 components
        self.writer_context_builder = WriterContextBuilder(
            self.memory, self.vector, config,
        )
        self.writer = SceneWriter(self.llm, config, fallback_llm=self.agent_llm)
        self.evaluator = SceneEvaluator(self.memory, config, llm_interface=self.agent_llm)
        self.summarizer = SceneSummarizer(llm_interface)
        self.committer = SceneCommitter(
            self.memory, self.vector, self.summarizer, project_path,
        )

        # Phase 5 components
        self.tension_evaluator = TensionEvaluator(config)

        # Quality scoring (黄金三章打磨闭环)
        self.scorer = ScoringEvaluator(self.agent_llm, config)

        # Plot-first components
        self.plot_manager = PlotOutlineManager(self.project_path, llm_interface)
        
        # Async post-processing
        self._async_update_thread: Optional[threading.Thread] = None

        # Load state
        self.state = self._load_state()

    def _init_agent_llm(self, llm_interface, config: dict, backend_type: str):
        """Initialise the agent LLM for evaluator / extractor tasks.

        When no separate extractor model is configured (empty string or
        same as the main model), reuses *self.llm* so both task groups
        share one API connection — the common case in cloud deployments.

        When a different model is configured (e.g. a local Ollama server
        for cost efficiency), attempts to initialise it.  If that model
        is unreachable the initialisation falls back to *self.llm*.
        """
        from ..tools.provider import LLMProvider

        # Router disabled → single-LLM mode
        if not self._router.enabled:
            logger.info("Router disabled — agent_llm reuses main LLM")
            return self.llm

        extractor_model = self._router.get_model_for_task("extractor")

        # Empty or same as main model → reuse the existing connection
        if not extractor_model:
            logger.info("No extractor model configured — agent_llm reuses main LLM")
            return self.llm

        main_model = config.get("llm.model", "")
        if extractor_model == main_model:
            logger.info(
                "Extractor model matches main (%s) — agent_llm reuses main LLM",
                main_model,
            )
            return self.llm

        # Different model configured → try to initialise it
        try:
            _agent_raw = self._router.get_interface_for_task("extractor")
            agent = LLMProvider(_agent_raw, "api")
            logger.info(
                "Agent LLM: %s (backend=%s)",
                extractor_model,
                self._router.get_backend_for_task("extractor"),
            )
            return agent
        except Exception as exc:
            logger.warning(
                "Agent LLM init failed (%s), falling back to main LLM", exc
            )
            return self.llm

    def _load_state(self) -> dict:
        """Load project state from state.json."""
        state_file = self.project_path / "state.json"
        with open(state_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_state(self):
        self.state["last_updated"] = datetime.utcnow().isoformat() + "Z"
        from ..utils.file_ops import write_json
        write_json(str(self.project_path / "state.json"), self.state)

    def _auto_checkpoint(self):
        """Auto-save checkpoint every 3 scenes.

        Uses the actual scene count (from scene_*.md files) rather than
        ``current_tick``, so the checkpoint label always matches the
        number of completed scenes regardless of tick semantics.
        """
        scene_files = list(self.project_path.glob("scenes/scene_*.md"))
        scene_count = len(scene_files)
        if scene_count > 0 and scene_count % 3 == 0:
            # 避免同一场景数重复存档
            if getattr(self, "_last_auto_checkpoint_count", 0) == scene_count:
                return
            try:
                from ..memory.checkpoint import create_checkpoint
                checkpoint_id = create_checkpoint(self.project_path, scene_count, "auto")
                self._last_auto_checkpoint_count = scene_count
                logger.info("Auto-checkpoint saved: %s (%d scenes)", checkpoint_id, scene_count)
            except Exception as e:
                logger.warning("Auto-checkpoint failed at %d scenes: %s", scene_count, e)

    def tick(self, notes: str = "") -> Dict[str, Any]:
        """Execute one story generation tick.

        Args:
            notes: Optional direction notes for this tick only.
                   Injected into both planner and writer contexts to
                   allow on-the-fly scene steering (if-lines, tone
                   shifts, POV experiments, etc.).  Overrides the
                   project-level ``generation.writer_notes`` config
                   for this tick when non-empty.

        Returns:
            Result dictionary with tick info and success status
        """
        self._tick_notes = notes
        tick = self.state["current_tick"]
        if tick == 0:
            return self._first_tick()
        else:
            return self._normal_tick()
    
    def _normal_tick(self) -> Dict[str, Any]:
        """Execute normal tick (tick 1+)."""
        tick = self.state["current_tick"]

        # 等待上次异步后处理完成（确保本 tick 读取最新数据）
        self._join_async_update()

        try:
            current_beat = self._resolve_plot_beat(tick)

            # Phase 1: Plan
            context = self.context_builder.build_planner_context(self.state, current_beat=current_beat, notes=getattr(self, '_tick_notes', ''))
            for plan_attempt in range(3):
                try:
                    plan = self._generate_plan(context)
                    validate_plan(plan)
                    self._enforce_beat_target(plan, current_beat)
                    self._enforce_pacing(plan, tick)
                    self._enforce_threads(plan, tick)
                    self._enforce_tool_usage(plan)
                    break
                except ValueError as e:
                    if plan_attempt < 2:
                        logger.warning("计划被拒 (尝试%d/3): %s", plan_attempt + 1, e)
                        context = self.context_builder.build_planner_context(
                            self.state, current_beat=current_beat,
                            notes=getattr(self, '_tick_notes', ''),
                            rejection_feedback=str(e),
                        )
                    else:
                        raise
            execution_results = self.executor.execute_plan(plan, tick)
            self._set_active_char(execution_results, plan)
            self.plan_manager.save_plan(tick, plan, execution_results, context)

            # Phase 2: Write + Evaluate (with retry on failure)
            # 黄金三章打磨闭环：前N章质量分不达标则自动重写
            scene_data, eval_result, quality_info = self._write_with_quality_loop(
                plan, execution_results, tick,
            )

            # Phase 3: Commit
            tension = self.tension_evaluator.evaluate_tension(scene_data["text"], writer_context)
            scene_id = self.committer.commit_scene(scene_data, tick, plan)

            # Phase 3: Post-commit
            self._save_qa(scene_id, tick, eval_result, plan, quality_info=quality_info)
            self._verify_beat(scene_id, plan, current_beat, scene_data, tick=tick)
            self._save_tension(scene_id, tension)

            # Phase 4: Memory update (异步后台执行，不阻塞用户反馈)
            promotion_result = self._check_goal_promotion(tick)

            async_cfg = self.config.get("generation", {}).get("async_post_process", True)
            if async_cfg:
                self._async_update_thread = threading.Thread(
                    target=self._async_update_wrapper,
                    args=(scene_data["text"], scene_id, tick, plan),
                    daemon=True,
                )
                self._async_update_thread.start()
            else:
                self._update_memory(scene_data["text"], scene_id, tick)
                self._bump_loop_mentions(plan)
                self._advance_threads(plan, scene_id, tick)
                self._maybe_audit_threads(tick)

            self.state["current_tick"] += 1
            self._save_state()
            self._auto_checkpoint()

            return self._build_tick_result(
                tick, scene_id, scene_data, execution_results,
                eval_result, tension, promotion_result,
                quality_info=quality_info,
            )

        except RuntimeError as e:
            execution_results = getattr(e, 'execution_results', {
                "tick": tick, "actions_executed": [], "errors": [str(e)], "success": False
            })
            plan = getattr(e, 'plan', {})
            self.plan_manager.save_error(tick, e, plan, execution_results)
            raise

        except Exception as e:
            logger.exception("tick %d 失败: %s", tick, e)
            self.plan_manager.save_error(tick, e, {}, {})
            raise

    # ---- tick pipeline helpers ----

    def _enforce_beat_target(self, plan: dict, current_beat) -> None:
        """Reject plans that don't target the current beat in strict mode."""
        if current_beat is None:
            return
        mode = self.config.get("plot", {}).get("beat_mode", "soft_hint")
        allow_skip = self.config.get("generation", {}).get("allow_beat_skip", False)
        fallback = self.config.get("generation", {}).get("fallback_to_reactive", True)

        # Only enforce when strict: guided mode + no skip + no fallback
        if mode not in ("guided", "strict") or allow_skip or fallback:
            return

        beat_target = plan.get("beat_target", {}) or {}
        target_id = beat_target.get("beat_id")
        strategy = beat_target.get("strategy")

        if not target_id or target_id != current_beat.id:
            raise ValueError(
                f"节拍强制：计划必须指定 beat_target.beat_id = {current_beat.id}，"
                f"当前为 beat_target={beat_target}"
            )
        # 宽松校验：不是 direct 就提醒但不中断（数据驱动，不硬编码策略名）
        known_direct = {"direct", "直接"}
        if strategy and strategy.lower() not in known_direct:
            logger.warning("节拍策略非direct: %s，继续执行", strategy)
        logger.info("节拍强制通过：%s (strategy=%s)", current_beat.id, strategy)

    def _enforce_pacing(self, plan: dict, tick: int) -> None:
        """Reject plans that repeat the same progress_step too many times."""
        if tick < 2:
            return
        mode = self.config.get("plot", {}).get("beat_mode", "soft_hint")
        if mode == "off":
            return
        current_step = plan.get("progress_step", "")
        if not current_step:
            return
        prev_steps = []
        for t in range(tick - 1, max(0, tick - 3), -1):
            try:
                prev_plan = self.plan_manager.load_plan(t)
                if prev_plan:
                    pdata = prev_plan.get("plan", {}) if isinstance(prev_plan, dict) else {}
                    step = pdata.get("progress_step", "")
                    if step:
                        prev_steps.append(step)
            except Exception:
                continue
        if len(prev_steps) < 2:
            return
        if len(set(prev_steps)) == 1 and current_step == prev_steps[0]:
            alts = {"revelation": "decision 或 setup",
                    "complication": "decision 或 resolution",
                    "decision": "revelation 或 complication",
                    "setup": "revelation 或 complication",
                    "resolution": "setup 或 complication"}
            suggestion = alts.get(current_step, "其他类型")
            raise ValueError(
                f"节奏约束：连续 {len(prev_steps)} 章 progress_step 都是 "
                f"'{current_step}'。本章必须使用不同的 step，"
                f"建议使用 '{suggestion}'。给故事喘息空间。"
            )

    def _enforce_tool_usage(self, plan: dict) -> None:
        """工具使用校验 — 动态读取注册表，带完整使用指南。

        规则：
        1. memory.search 必调
        2. 至少 2 个工具（search + 至少一个实体操作）
        失败时输出完整工具指南，教 LLM 什么时候该用什么工具。
        """
        actions = plan.get("actions", [])
        tools_called = {a.get("tool", "") for a in actions}
        reasons = []

        if "memory.search" not in tools_called:
            reasons.append(
                "❌ 缺少 memory.search — 每场景必须先用它搜索已有角色/地点/阵营/线索，"
                "否则会凭空编造、与已有内容脱节。"
            )

        if len(actions) < 2:
            reasons.append(
                "❌ 工具调用不足 — search 之后请至少再选一个实体维护工具：\n"
                "\n"
                "  全部可用工具及使用时机：\n"
                "\n"
                "【查询类 — 获取已有信息】\n"
                "• memory.search — 语义搜索已有角色/地点/场景/阵营/线索\n"
                "  何时用：每场景开始时，用场景关键词搜索，了解已有什么\n"
                "• relationship.query — 查询某角色的所有关系\n"
                "  何时用：写角色互动前，先看看 Ta 和别人的关系网\n"
                "• faction.query — 搜索阵营/势力\n"
                "  何时用：场景涉及组织/势力时，先查已有阵营信息\n"
                "\n"
                "【创建类 — 场景中出现新的东西时用】\n"
                "• character.generate — 创建新角色\n"
                "  何时用：场景中出现了故事里还不存在的角色\n"
                "  不调会：角色数据丢失，后续无法搜索和引用\n"
                "• location.generate — 创建新地点\n"
                "  何时用：场景发生在新的、未记录的地点\n"
                "  不调会：地点数据丢失，场景背景无法被后续搜索\n"
                "• faction.generate — 创建新阵营/势力\n"
                "  何时用：场景引入了新的组织、帮派、机构等\n"
                "• relationship.create — 建立两个角色的关系\n"
                "  何时用：两个角色首次互动（对话/冲突/合作/见面）\n"
                "  不调会：角色关系网缺失，后续互动缺少上下文\n"
                "\n"
                "【更新类 — 已有实体发生变化时用】\n"
                "• relationship.update — 更新角色关系状态\n"
                "  何时用：已有关系发生变化（冷淡→亲密、友好→敌对等）\n"
                "• faction.update — 更新阵营信息\n"
                "  何时用：阵营的立场/资源/策略发生变化\n"
                "\n"
                "  自检：读完 scene_intention，问问自己——\n"
                "  有新角色吗？ → character.generate\n"
                "  有新地点吗？ → location.generate\n"
                "  角色互动了吗？ → relationship.create 或 relationship.update\n"
                "  涉及势力了吗？ → faction.query 或 faction.generate"
            )

        if reasons:
            raise ValueError(
                "管线工具校验不通过：\n" + "\n".join(reasons)
            )

    def _enforce_threads(self, plan: dict, tick: int) -> None:
        forced_ids = self.thread_manager.get_forced_ids(tick)
        if not forced_ids:
            return
        addressed = set(plan.get("threads_addressed", []) or [])
        for tid in forced_ids:
            if tid in addressed:
                continue
            thread = self.memory.load_thread(tid)
            name = thread.name if thread else tid
            stall = tick - (thread.last_advanced_tick or thread.introduced_tick) if thread else 0
            raise ValueError(
                f"支线 {tid}「{name}」已停滞 {stall} 章，必须在本章推进。"
                f"请在计划 JSON 的 threads_addressed 字段中列出 {tid}。"
            )

    def _maybe_audit_threads(self, tick: int) -> None:
        from ..configs.constants import THREAD_AUDIT_INTERVAL
        if tick <= 0 or tick % THREAD_AUDIT_INTERVAL != 0:
            return
        try:
            suggestions = self.thread_manager.run_audit(tick, self.state.get("novel_name", ""))
            if suggestions:
                logger.info("支线审计发现 %d 条新建议（pending），等待用户确认", len(suggestions))
        except Exception as exc:
            logger.warning("支线审计失败 (tick %d): %s", tick, exc)

    def _resolve_plot_beat(self, tick: int):
        """Manage plot-first beat lifecycle: regenerate if needed, return current beat."""
        start_tick = self.config.get('generation.plot_first_start_tick', 2)
        if tick < start_tick:
            return None
        # 有待执行节拍时自动启用；config 可显式覆盖为 False 关闭
        use_plot_first = self.config.get('generation.use_plot_first', True)
        if not use_plot_first:
            return None

        if self._needs_beat_regeneration():
            logger.info("正在生成情节节拍...")
            try:
                beats = self.plot_manager.generate_next_beats(
                    count=self.config.get('generation.plot_beats_ahead', 5)
                )
                self.plot_manager.add_beats(beats)
                logger.info("已生成 %d 个新情节节拍", len(beats))
            except (ValueError, json.JSONDecodeError, RuntimeError) as e:
                logger.warning("Beat generation failed: %s", e)
                if not self.config.get('generation.fallback_to_reactive', True):
                    raise

        beat = self.plot_manager.get_next_beat()
        if beat:
            logger.info("执行节拍：%s", beat.description)
        elif not self.config.get('generation.fallback_to_reactive', True):
            raise RuntimeError("No plot beats available and fallback disabled")
        return beat

    def _set_active_char(self, execution_results, plan):
        plan_pov = plan.get("pov_character", "")
        current_active = self.state.get("active_character")

        # POV switch: planner selected a different existing character
        if plan_pov and plan_pov.startswith("C") and plan_pov != current_active:
            target = self.memory.load_character(plan_pov)
            if target:
                logger.info("POV 切换: %s -> %s", current_active, plan_pov)
                self.state["active_character"] = plan_pov
                target.pov_count = getattr(target, "pov_count", 0) + 1
                self.memory.save_character(target)
                return

        # First tick: set from character.generate result
        if current_active is not None:
            return
        for action in execution_results.get("actions_executed", []):
            if action.get("tool") == "character.generate" and action.get("success"):
                char_id = action.get("result", {}).get("character_id")
                if char_id:
                    self.state["active_character"] = char_id
                    if plan_pov and not plan_pov.startswith("C"):
                        plan["pov_character"] = char_id
                    char = self.memory.load_character(char_id)
                    if char:
                        char.pov_count = getattr(char, "pov_count", 0) + 1
                        self.memory.save_character(char)
                    break

    def _save_qa(self, scene_id, tick, eval_result, plan, quality_info=None):
        if not eval_result and not quality_info:
            return
        try:
            self.memory.save_scene_qa(scene_id, tick, eval_result, quality=quality_info)
        except (IOError, OSError) as e:
            logger.warning("Failed to save scene QA: %s", e)
        try:
            self._update_beats_from_evaluation(scene_id, plan, eval_result, tick=tick)
        except (IOError, OSError, AttributeError, ValueError) as e:
            logger.warning("Failed to update beats from evaluation: %s", e)

    def _verify_beat(self, scene_id, plan, current_beat, scene_data, tick=None):
        if not current_beat:
            return
        logger.info("   验证节拍执行情况...")
        beat_target = plan.get("beat_target", {}) or {}
        planner_targeted = beat_target.get("beat_id") == current_beat.id
        semantic_score = self.vector.compute_semantic_similarity(
            current_beat.description, scene_data["text"][:3000]
        )

        if planner_targeted:
            self._mark_beat_complete(current_beat.id, scene_id,
                                     tick=tick,
                                     verification_score=semantic_score,
                                     verification_method="trusted_planner")
            logger.info("        [v] 节拍 %s 已完成（规划器确认，得分=%.2f）", current_beat.id, semantic_score)
            if semantic_score < BEAT_LOW_CONFIDENCE_THRESHOLD:
                logger.info("        [WARN]  置信度较低，建议人工复核")
        elif self.config.get('generation.verify_beat_execution', True):
            threshold = self.config.get('generation.beat_verification_threshold', 0.5)
            if semantic_score >= threshold:
                self._mark_beat_complete(current_beat.id, scene_id,
                                         tick=tick,
                                         verification_score=semantic_score,
                                         verification_method="semantic")
                logger.info("        [v] 节拍 %s 已完成（语义匹配，得分=%.2f）", current_beat.id, semantic_score)
            else:
                logger.info("        [WARN]  节拍可能未完全执行（得分=%.2f < %s）", semantic_score, threshold)
                if not self.config.get('generation.allow_beat_skip', False):
                    logger.info("        节拍 %s 保持待执行状态", current_beat.id)
        else:
            self._mark_beat_complete(current_beat.id, scene_id,
                                     tick=tick,
                                     verification_score=semantic_score,
                                     verification_method="auto")

    def _save_tension(self, scene_id, tension_result):
        if not tension_result.get('enabled'):
            return
        scene = self.memory.load_scene(scene_id)
        if not scene:
            return
        scene.tension_level = tension_result['tension_level']
        scene.tension_category = tension_result['tension_category']
        self.memory.save_scene(scene)
        logger.info("        张力：%s/10（%s）", tension_result['tension_level'], tension_result['tension_category'])

    def _join_async_update(self):
        """等待上次异步后处理完成（如有）。"""
        if self._async_update_thread is not None:
            if self._async_update_thread.is_alive():
                logger.debug("等待上次异步后处理完成...")
                self._async_update_thread.join(timeout=30)
            self._async_update_thread = None

    def _async_update_wrapper(self, scene_text: str, scene_id: str, tick: int, plan: dict):
        """异步后处理入口 — 包裹完整 Phase 4 逻辑。"""
        try:
            self._update_memory(scene_text, scene_id, tick)
            self._bump_loop_mentions(plan)
            self._advance_threads(plan, scene_id, tick)
            self._maybe_audit_threads(tick)
            logger.debug("异步后处理完成 (tick %d)", tick)
        except Exception as e:
            logger.warning("异步后处理失败 (tick %d): %s", tick, e)

    def _update_memory(self, scene_text: str, scene_id: str, tick: int):
        """Post-processing: facts, entities, lore, characters via memory/update.py."""
        from ..memory.update import update_from_scene
        try:
            update_from_scene(scene_text, scene_id, tick, self.state, self.memory, self.agent_llm, self.config)
        except Exception as e:
            logger.warning("内存更新失败 (tick %d): %s", tick, e)

    def _write_with_quality_loop(
        self, plan: dict, execution_results: dict, tick: int,
    ) -> tuple:
        """Write + Evaluate + 质量打磨闭环。

        先按原有逻辑 write → eval（pass/fail 检查）。
        如果通过且开启了质量打磨，再用 Scorer 打分：不达标则带反馈重写。

        Returns: (scene_data, eval_result, quality_info)
        """
        max_retries = self.config.get("generation", {}).get("eval_max_retries", 2)
        eval_feedback = ""
        scene_data = None
        eval_result = None
        quality_info = {}  # quality_score, polish_rounds

        # ---- Stage 1: 合规评估（原有逻辑） ----
        for attempt in range(max_retries + 1):
            writer_context = self.writer_context_builder.build_writer_context(
                plan, execution_results, self.state, eval_feedback=eval_feedback,
                notes=getattr(self, '_tick_notes', ''),
            )
            scene_data = self.writer.write_scene(writer_context)
            eval_result = self.evaluator.evaluate_scene(scene_data["text"], writer_context)
            if eval_result["passed"] or not eval_result.get("issues"):
                break
            if attempt < max_retries:
                logger.warning("评估失败 (第%d次)，带反馈重试...", attempt + 1)
                eval_feedback = _format_eval_feedback(eval_result)
            else:
                raise ValueError(
                    f"Scene evaluation failed after {max_retries + 1} attempts: "
                    f"{eval_result['issues']}"
                )

        # ---- Stage 2: 质量打磨（前N章） ----
        if self.scorer.is_quality_tick(tick):
            threshold = self.scorer.get_threshold(tick)
            max_polish = self.scorer.max_polish_rounds
            quality_feedback = ""
            polish_rounds = 0

            for polish_round in range(max_polish):
                score_result = self.scorer.score_scene(scene_data["text"], writer_context)
                total = score_result.get("total", 0)
                if total >= threshold:
                    logger.info("质量打磨通过: %d/100 ≥ %d (tick %d, 第%d轮)",
                                total, threshold, tick, polish_round + 1)
                    quality_info = {"quality_score": total, "polish_rounds": polish_round + 1}
                    break

                logger.info("质量打磨第%d轮: %d/100 < %d (tick %d)，带反馈重写...",
                            polish_round + 1, total, threshold, tick)
                quality_feedback = self.scorer.format_feedback(score_result)

                # 带质量反馈重建 context 并重写
                writer_context = self.writer_context_builder.build_writer_context(
                    plan, execution_results, self.state,
                    eval_feedback=quality_feedback,
                    notes=getattr(self, '_tick_notes', ''),
                )
                scene_data = self.writer.write_scene(writer_context)
                # 重写后仍需通过合规评估
                eval_result = self.evaluator.evaluate_scene(
                    scene_data["text"], writer_context,
                )
                polish_rounds = polish_round + 1

            if not quality_info:
                quality_info = {"quality_score": total, "polish_rounds": polish_rounds + 1}

        return scene_data, eval_result, quality_info

    def _build_tick_result(self, tick, scene_id, scene_data, execution_results,
                           eval_result, tension_result, promotion_result=None, quality_info=None):
        result = {
            "success": True,
            "tick": tick,
            "scene_id": scene_id,
            "scene_file": f"scenes/scene_{tick:03d}.md",
            "word_count": scene_data["word_count"],
            "actions_executed": len(execution_results.get("actions_executed", [])),
            "eval_warnings": eval_result.get("warnings", []),
        }
        if promotion_result:
            result["goal_promoted"] = promotion_result
        if tension_result.get('enabled'):
            result["tension"] = {
                "level": tension_result['tension_level'],
                "category": tension_result['tension_category']
            }
        if quality_info:
            result["quality_score"] = quality_info.get("quality_score")
            result["polish_rounds"] = quality_info.get("polish_rounds")
        return result

    def _auto_fill_foundation(self):
        """Auto-fill missing story foundation fields via LLM inference.

        Only fills themes and primary_goal if they are empty. Uses existing
        genre, premise, protagonist_archetype, setting, and tone to infer.
        """
        foundation = self.state.get("story_foundation", {})
        if not foundation:
            return

        themes = foundation.get("themes") or []
        primary_goal = foundation.get("primary_goal") or ""

        if isinstance(themes, list) and len(themes) > 0 and primary_goal:
            return  # Nothing to fill

        logger.info("   自动补全故事基础设定（themes/primary_goal）...")
        genre = foundation.get("genre", "")
        premise = foundation.get("premise", "")
        protagonist = foundation.get("protagonist_archetype", "")
        setting = foundation.get("setting", "")
        tone = foundation.get("tone", "")

        prompt = (
            "你是一个故事设定助理。根据以下已有的故事信息，补全缺失的设定项。\n\n"
            f"已有信息：\n"
            f"- 类型：{genre}\n"
            f"- 前提：{premise}\n"
            f"- 主角设定：{protagonist}\n"
            f"- 世界背景：{setting}\n"
            f"- 基调：{tone}\n\n"
            "请输出JSON：\n"
            '{"themes": ["主题1", "主题2", "主题3"], "primary_goal": "主角的核心目标，一句话描述"}\n\n'
            "要求：\n"
            "- 主题3-5个，每个2-6字中文，要具体不空洞\n"
            "- 核心目标要具体，与前提紧密相关，能从前提中自然推导\n"
            "- 如果已有主题或目标不为空，保留原有内容\n"
            "只返回JSON。"
        )

        try:
            response = self.llm.generate(prompt, max_tokens=200)
            data = self._parse_plan_response(response)
            if data:
                new_themes = data.get("themes", [])
                new_goal = data.get("primary_goal", "")

                if isinstance(new_themes, list) and len(new_themes) > 0 and not themes:
                    foundation["themes"] = new_themes
                    logger.info("   [+] 补全 themes: %s", ", ".join(new_themes))

                if new_goal and not primary_goal:
                    foundation["primary_goal"] = new_goal
                    logger.info("   [+] 补全 primary_goal: %s", new_goal)

                if foundation is not self.state.get("story_foundation", {}):
                    self.state["story_foundation"] = foundation
                    self._save_state()
        except Exception as e:
            logger.warning("   [-] 自动补全 foundation 失败: %s", e)

    def _first_tick(self) -> Dict[str, Any]:
        """Execute first tick with world baseline + two-phase entity generation.

        Phase 0: Generate world rules from foundation (lore baseline)
        Phase 1: Generate entities (character, location)
        Phase 2: Write scene with established entities
        """
        tick = 0

        logger.info("     执行第0幕（三阶段初始化）...")

        try:
            # Index any existing loops from disk into vector store
            existing_loops = self.memory.load_open_loops()
            for loop in existing_loops:
                try:
                    self.vector.index_loop(loop)
                except Exception:
                    pass

            # Auto-fill missing story foundation fields
            self._auto_fill_foundation()

            # PHASE 0: World Baseline
            logger.info("   阶段零：生成世界观基线...")
            foundation = self.state.get("story_foundation", {})
            genre = foundation.get("genre", "")
            premise = foundation.get("premise", "")
            setting = foundation.get("setting", "")
            tone = foundation.get("tone", "")
            protagonist = foundation.get("protagonist_archetype", "")
            themes = foundation.get("themes", [])
            primary_goal = foundation.get("primary_goal", "")
            themes_str = ", ".join(themes) if isinstance(themes, list) else str(themes or "")

            lore_prompt = (
                f"为以下故事设定生成初始世界观规则。\n\n"
                f"类型：{genre}\n前提：{premise}\n背景：{setting}\n基调：{tone}\n"
                f"主角：{protagonist or '（待定——由你根据上述设定自由创作）'}\n"
                f"主题：{themes_str or '（待定）'}\n"
                f"主角目标：{primary_goal or '（待定）'}\n\n"
                f"请生成 3-5 条核心世界观规则，每条包含：\n"
                f"- 类别：根据故事语境自行取名（如 魔法体系/科技水平/社会结构 等），不要用固定枚举\n"
                f"- 类型：根据本条目的性质自行归类（如 规则/事实/约束/能力/限制 等）\n"
                f"- 内容：一句话描述，中文\n"
                f"- 重要性：关键/重要/普通/次要\n\n"
                f"返回JSON：{{\"lore\":[{{\"type\":\"规则\",\"category\":\"...\",\"content\":\"...\",\"importance\":\"重要\"}},...]}}\n"
                f"只返回JSON。"
            )
            try:
                from ..memory.entities import Lore
                lore_resp = self.llm.generate(lore_prompt, max_tokens=500)
                lore_data = self._parse_plan_response(lore_resp)
                for item in lore_data.get("lore", []):
                    lid = f"L{len(self.memory.load_all_lore()):03d}"
                    lore_obj = Lore(
                        id=lid,
                        lore_type=item.get("type", "rule"),
                        content=item.get("content", ""),
                        category=item.get("category", "other"),
                        importance=item.get("importance", "normal"),
                        source_scene_id="world_baseline",
                        tick=0,
                    )
                    self.memory.save_lore(lore_obj)
                count = len(lore_data.get("lore", []))
                if count:
                    logger.info("   → 已生成 %d 条世界观基线", count)
            except Exception as e:
                logger.warning("   世界观基线生成失败: %s", e)

            # PHASE 1: Entity Generation
            logger.info("   阶段一：生成实体...")

            # Step 1: Gather context
            logger.info("   1. 收集上下文...")
            context = self.context_builder.build_planner_context(self.state)

            # Step 2: Generate plan
            logger.info("   2. 生成故事计划...")
            plan = self._generate_plan(context)

            # Step 3: Validate plan
            logger.info("   3. 验证计划...")
            validate_plan(plan)

            # Step 4: Execute ONLY entity generation tools
            logger.info("   4. 预生成实体...")
            entity_results = self._execute_entity_generation_only(plan, tick)

            # Step 5: Update plan with real entity IDs
            logger.info("   5. 将实体ID写入计划...")
            self._update_plan_with_entity_ids(plan, entity_results)
            
            self._set_active_char(entity_results, plan)
            
            # PHASE 2: Scene Writing
            logger.info("   阶段二：撰写场景...")

            # Step 7: Execute remaining tools (if any)
            logger.info("   6. 执行剩余工具...")
            remaining_results = self._execute_remaining_tools(plan, tick, entity_results)
            
            # Merge results
            execution_results = self._merge_execution_results(entity_results, remaining_results)
            
            # Step 8: Store plan
            logger.info("   7. 保存计划...")
            plan_file = self.plan_manager.save_plan(tick, plan, execution_results, context)

            # Step 9: Write scene with retry + quality polish loop
            logger.info("   8. 撰写场景正文...")
            scene_data, eval_result, quality_info = self._write_with_quality_loop(
                plan, execution_results, tick,
            )

            logger.info("   10. 提交场景...")
            scene_id = self.committer.commit_scene(scene_data, tick, plan)

            if eval_result or quality_info:
                try:
                    self.memory.save_scene_qa(scene_id, tick, eval_result, quality=quality_info)
                except (IOError, OSError) as e:
                    logger.warning("Failed to save scene QA (first tick): %s", e)
                try:
                    self._update_beats_from_evaluation(scene_id, plan, eval_result)
                except (IOError, OSError, AttributeError, ValueError) as e:
                    logger.warning("Failed to update beats from evaluation (first tick): %s", e)

            # Post-processing via memory/update.py
            self._update_memory(scene_data["text"], scene_id, tick)
            self.vector.index_scene(self.memory.load_scene(scene_id))

            # Increment tick
            self.state["current_tick"] += 1
            self._save_state()
            self._auto_checkpoint()

            return {
                "success": True,
                "tick": tick,
                "scene_id": scene_id,
                "scene_file": f"scenes/scene_{tick:03d}.md",
                "word_count": scene_data["word_count"],
                "plan_file": str(plan_file),
                "actions_executed": len(execution_results.get("actions_executed", []))
            }
        
        except RuntimeError as e:
            # Tool execution error
            execution_results = getattr(e, 'execution_results', {
                "tick": tick,
                "actions_executed": [],
                "errors": [str(e)],
                "success": False
            })
            
            plan = getattr(e, 'plan', {})
            self.plan_manager.save_error(tick, e, plan, execution_results)
            raise
        
        except Exception as e:
            # Other errors
            self.plan_manager.save_error(tick, e, {}, {})
            raise
    
    def _execute_entity_generation_only(self, plan: Dict, tick: int) -> Dict:
        """Execute only entity generation tools from plan.
        
        Args:
            plan: The generated plan
            tick: Current tick number
        
        Returns:
            Execution results for entity generation tools only
        """
        entity_tools = ["name.generate", "character.generate", "location.generate"]
        
        filtered_actions = [
            action for action in plan.get("actions", [])
            if action.get("tool") in entity_tools
        ]
        
        if not filtered_actions:
            return {"actions_executed": [], "errors": [], "success": True}
        
        # Create temporary plan with only entity actions
        entity_plan = {**plan, "actions": filtered_actions}
        
        return self.executor.execute_plan(entity_plan, tick)
    
    def _execute_remaining_tools(self, plan: Dict, tick: int, entity_results: Dict) -> Dict:
        """Execute non-entity tools from plan.
        
        Args:
            plan: The generated plan (with updated entity IDs)
            tick: Current tick number
            entity_results: Results from entity generation
        
        Returns:
            Execution results for remaining tools
        """
        entity_tools = ["name.generate", "character.generate", "location.generate"]
        
        remaining_actions = [
            action for action in plan.get("actions", [])
            if action.get("tool") not in entity_tools
        ]
        
        if not remaining_actions:
            return {"actions_executed": [], "errors": [], "success": True}
        
        # Create temporary plan with only remaining actions
        remaining_plan = {**plan, "actions": remaining_actions}
        
        return self.executor.execute_plan(remaining_plan, tick)
    
    def _update_plan_with_entity_ids(self, plan: Dict, entity_results: Dict):
        """Update plan with real entity IDs after generation.
        
        Args:
            plan: The plan to update (modified in place)
            entity_results: Results from entity generation
        """
        for action in entity_results.get("actions_executed", []):
            if action.get("tool") == "character.generate" and action.get("success"):
                char_id = action.get("result", {}).get("character_id")
                if char_id and plan.get("pov_character"):
                    # Replace placeholder with real ID
                    if not plan["pov_character"].startswith("C"):
                        plan["pov_character"] = char_id
            
            elif action.get("tool") == "location.generate" and action.get("success"):
                loc_id = action.get("result", {}).get("location_id")
                if loc_id and plan.get("target_location"):
                    # Replace placeholder with real ID
                    if not plan["target_location"].startswith("L"):
                        plan["target_location"] = loc_id
    
    def _merge_execution_results(self, entity_results: Dict, remaining_results: Dict) -> Dict:
        """Merge entity and remaining execution results.
        
        Args:
            entity_results: Results from entity generation
            remaining_results: Results from remaining tools
        
        Returns:
            Combined execution results
        """
        return {
            "actions_executed": (
                entity_results.get("actions_executed", []) +
                remaining_results.get("actions_executed", [])
            ),
            "errors": (
                entity_results.get("errors", []) +
                remaining_results.get("errors", [])
            ),
            "success": entity_results.get("success", True) and remaining_results.get("success", True)
        }
    
    def _update_beats_from_evaluation(self, scene_id: str, plan: Dict[str, Any], eval_result: Dict[str, Any], tick: int = None) -> None:
        if isinstance(self.config, dict):
            mode = self.config.get("plot", {}).get("beat_mode", "soft_hint")
        else:
            mode = self.config.get("plot.beat_mode", "soft_hint")
        if mode != "guided":
            return
        beat_target = plan.get("beat_target") or {}
        if not isinstance(beat_target, dict):
            return
        beat_id = beat_target.get("beat_id")
        if not beat_id:
            return
        alignment = eval_result.get("beat_hint_alignment") or {}
        if not isinstance(alignment, dict):
            return
        if alignment.get("beat_id") != beat_id:
            return
        label = alignment.get("label")
        if label not in ("medium", "high"):
            return
        score = alignment.get("score")
        try:
            manager = PlotOutlineManager(self.project_path)
            outline = manager.load_outline()
        except (FileNotFoundError, IOError, json.JSONDecodeError) as e:
            logger.warning("Failed to load outline: %s", e)
            return
        updated = False
        for beat in outline.beats:
            if getattr(beat, "id", None) == beat_id:
                # Mark beat as completed for consistency with CLI summary,
                # while keeping executed_in_scene/execution_notes as metadata.
                setattr(beat, "status", "completed")
                setattr(beat, "executed_in_scene", scene_id)
                if tick is not None:
                    setattr(beat, "consumed_at_tick", tick)
                notes = getattr(beat, "execution_notes", "") or ""
                extra = f"Executed in {scene_id} with alignment {label}"
                if isinstance(score, (int, float)):
                    extra += f" (score={score})"
                if notes:
                    notes = notes.rstrip()
                    extra = notes + " " + extra
                setattr(beat, "execution_notes", extra)
                updated = True
                break
        if updated:
            try:
                manager.save_outline(outline)
            except (IOError, OSError) as e:
                logger.warning("Failed to save outline: %s", e)

    def _generate_plan(self, context: dict) -> dict:
        """Generate a plan using the planner LLM."""
        max_tokens = self.config.get('llm.planner_max_tokens', 2000)
        if self.llm.backend_type == "anthropic":
            messages = [
                {"role": "system", "content": [
                    {"type": "text", "text": SYSTEM_PLANNER,
                     "cache_control": {"type": "ephemeral"}}
                ]},
                {"role": "user", "content": format_planner_prompt(context)}
            ]
            response = self.llm.chat(messages, max_tokens=max_tokens)
        else:
            response = self.llm.generate(format_planner_prompt(context), max_tokens=max_tokens)
        return self._parse_plan_response(response)
    
    def _parse_plan_response(self, response: str) -> dict:
        """Parse LLM response into plan dictionary.
        
        Args:
            response: Raw LLM response text
        
        Returns:
            Parsed plan dictionary
        
        Raises:
            ValueError: If JSON cannot be extracted or parsed
        """
        # Try to extract JSON from response
        # LLM might wrap it in markdown code blocks
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                raise ValueError("Could not extract JSON from LLM response")
        
        try:
            # Sanitize: strip control characters that break JSON (LLM may include raw \n etc)
            sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
            plan = json.loads(sanitized)
            return plan
        except json.JSONDecodeError as e:
            # Provide actionable feedback for LLM retry
            raise ValueError(
                f"JSON解析失败: {e}\n"
                f"请检查：1) 字符串内换行需要用 \\n 转义 "
                f"2) 引号需要成对出现 3) 不要输出 JSON 之外的内容"
            )
    
    def _check_goal_promotion(self, tick: int) -> dict:
        """Check if a story goal should be auto-promoted (Phase 7A.2).
        
        After 10-15 scenes, promote the most active protagonist-related loop
        to become the primary story goal. Skips if user specified a goal.
        
        Args:
            tick: Current tick number
            
        Returns:
            Dictionary with promotion info if promotion occurred, None otherwise
        """
        # Only check during the promotion window
        if tick < GOAL_PROMOTION_WINDOW_START or tick > GOAL_PROMOTION_WINDOW_END:
            return None
        
        # Check if already promoted or user-specified
        story_goals = self.state.get('story_goals', {})
        primary = story_goals.get('primary')
        if primary:
            # Don't auto-promote if user specified a goal or already promoted
            if primary.get('source') == 'user_specified':
                logger.debug("Primary goal was user-specified, skipping auto-promotion")
            return None
        
        # Get protagonist ID
        protagonist_id = self.state.get('active_character')
        if not protagonist_id:
            logger.debug("No protagonist set, skipping goal promotion")
            return None
        
        # Get all open loops
        open_loops = self.memory.get_open_loops()
        if not open_loops:
            logger.debug("No open loops, skipping goal promotion")
            return None
        
        # Find protagonist-related loops
        protagonist_loops = [
            loop for loop in open_loops
            if protagonist_id in (loop.related_characters or [])
        ]
        
        if not protagonist_loops:
            logger.debug("No protagonist-related loops, skipping goal promotion")
            return None
        
        # Find most mentioned loop (must have been mentioned at least 5 times)
        top_loop = max(
            protagonist_loops,
            key=lambda l: l.scenes_mentioned,
            default=None
        )
        
        if not top_loop or top_loop.scenes_mentioned < LOOP_MIN_MENTIONS_FOR_PROMOTION:
            logger.debug(f"Top loop only mentioned {top_loop.scenes_mentioned if top_loop else 0} times, need 5+")
            return None
        
        # Promote to story goal!
        top_loop.is_story_goal = True
        self.memory.save_open_loops([top_loop])
        
        # Update state
        story_goals['primary'] = {
            'loop_id': top_loop.id,
            'description': top_loop.description,
            'source': 'auto_promoted',
            'promoted_at_tick': tick
        }
        story_goals['promotion_tick'] = tick
        self.state['story_goals'] = story_goals
        
        logger.info(" 故事目标已浮现：%s", top_loop.description)
        
        return {
            'loop_id': top_loop.id,
            'description': top_loop.description,
            'tick': tick,
            'mentions': top_loop.scenes_mentioned
        }
    
    def _bump_loop_mentions(self, plan: dict) -> None:
        """Increment scenes_mentioned for open loops addressed in this scene."""
        loop_ids = set(plan.get("loops_addressed", []) or [])
        if not loop_ids:
            return
        loops = self.memory.load_open_loops()
        updated = False
        for loop in loops:
            if loop.id in loop_ids:
                loop.scenes_mentioned = getattr(loop, "scenes_mentioned", 0) + 1
                loop.last_mentioned_tick = self.state["current_tick"]
                updated = True
        if updated:
            self.memory.save_open_loops(loops)
            logger.debug("Bumped mentions for loops: %s", loop_ids)

    def _advance_threads(self, plan: dict, scene_id: str, tick: int) -> None:
        """Mark story threads as advanced when addressed in this scene."""
        thread_ids = plan.get("threads_addressed", []) or []
        if not thread_ids:
            return
        for tid in thread_ids:
            try:
                self.memory.advance_thread(tid, tick, scene_id)
            except Exception as e:
                logger.debug("Thread %s advance failed: %s", tid, e)

    def _needs_beat_regeneration(self) -> bool:
        """Check if we need to generate more plot beats (Phase 5).
        
        Returns:
            True if pending beats are below threshold
        """
        threshold = self.config.get('generation.plot_regeneration_threshold', 2)
        outline = self.plot_manager.load_outline()
        pending_count = sum(1 for beat in outline.beats if beat.status == "pending")
        return pending_count < threshold
    
    def _mark_beat_complete(
        self,
        beat_id: str,
        scene_id: str,
        tick: int = None,
        verification_score: float = None,
        verification_method: str = None
    ):
        """Mark a plot beat as completed (Phase 5).

        Args:
            beat_id: ID of the beat to mark complete
            scene_id: ID of the scene where beat was executed
            tick: Current tick number when beat was consumed
            verification_score: Optional confidence score (0.0-1.0)
            verification_method: How verification was done (trusted_planner, semantic, llm, manual)
        """
        try:
            outline = self.plot_manager.load_outline()
            for beat in outline.beats:
                if beat.id == beat_id:
                    beat.status = "completed"
                    beat.executed_in_scene = scene_id
                    beat.execution_notes = f"Executed in {scene_id}"
                    if tick is not None:
                        beat.consumed_at_tick = tick
                    if verification_score is not None:
                        beat.verification_score = verification_score
                    if verification_method:
                        beat.verification_method = verification_method
                    break
            self.plot_manager.save_outline(outline)
            logger.info("Marked beat %s as completed (score=%s, method=%s)", beat_id, verification_score, verification_method)
            
        except (FileNotFoundError, IOError, json.JSONDecodeError) as e:
            logger.error("Failed to mark beat complete: %s", e)
