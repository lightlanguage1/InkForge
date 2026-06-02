"""Streaming wrapper for StoryAgent — SSE event stream for tick progress."""

import json
import logging
from typing import Any, Generator

logger = logging.getLogger(__name__)


class StreamingStoryAgent:
    """Wrap StoryAgent to emit tick progress as SSE events.

    Each phase of the tick process is reported as a separate event,
    enabling real-time progress display in API consumers.
    """

    def __init__(self, agent: Any, notes: str = ""):
        self.agent = agent
        self.notes = notes

    def tick_stream(self) -> Generator[str, None, None]:
        tick = self.agent.state.get("current_tick", 0)
        self.agent._tick_notes = self.notes  # 注入到 agent.tick() 流程
        yield self._event("tick_start", {"tick": tick})
        try:
            if tick == 0:
                yield from self._stream_first_tick(tick)
            else:
                yield from self._stream_normal_tick(tick)
        except Exception as exc:
            logger.exception("Tick %s failed", tick)
            msg = str(exc)
            # Keep only the last meaningful line for display
            if "\n" in msg:
                lines = [l.strip() for l in msg.split("\n") if l.strip()]
                msg = lines[-1] if lines else msg.split("\n")[0]
            if len(msg) > 300:
                msg = msg[:300] + "..."
            yield self._event("tick_error", {"tick": tick, "error": msg})

    def _stream_normal_tick(self, tick: int) -> Generator[str, None, None]:
        """Stream a normal tick (tick 1+)."""
        current_beat = self.agent._resolve_plot_beat(tick)

        yield self._event("phase", {"name": "context", "tick": tick})

        # Plan with retry loop (same as agent._normal_tick)
        rejection_feedback = ""
        for plan_attempt in range(3):
            try:
                context = self.agent.context_builder.build_planner_context(
                    self.agent.state, current_beat=current_beat,
                    notes=getattr(self.agent, '_tick_notes', ''),
                    rejection_feedback=rejection_feedback if plan_attempt > 0 else "",
                )

                yield self._event("phase", {"name": "planning", "tick": tick})
                plan = self.agent._generate_plan(context)
                from .schemas import validate_plan
                validate_plan(plan)
                self.agent._enforce_beat_target(plan, current_beat)
                self.agent._enforce_pacing(plan, tick)
                self.agent._enforce_threads(plan, tick)
                self.agent._enforce_tool_usage(plan)
                break
            except ValueError as e:
                if plan_attempt < 2:
                    logger.warning("计划被拒 (尝试%d/3): %s", plan_attempt + 1, e)
                    rejection_feedback = str(e)
                else:
                    raise

        yield self._event("phase", {"name": "execution", "tick": tick})
        execution_results = self.agent.executor.execute_plan(plan, tick)
        self.agent._set_active_char(execution_results, plan)
        self.agent.plan_manager.save_plan(tick, plan, execution_results, context)

        yield self._event("phase", {"name": "writing", "tick": tick})
        writer_context = self.agent.writer_context_builder.build_writer_context(
            plan, execution_results, self.agent.state,
            notes=getattr(self.agent, '_tick_notes', ''),
        )

        yield self._event("phase", {"name": "generating", "tick": tick})
        scene_data = self.agent.writer.write_scene(writer_context)

        yield self._event("phase", {"name": "evaluation", "tick": tick})
        eval_result = self.agent.evaluator.evaluate_scene(
            scene_data["text"], writer_context
        )
        if not eval_result["passed"] and eval_result.get("issues"):
            raise ValueError(f"Scene evaluation failed: {eval_result['issues']}")

        yield self._event("phase", {"name": "tension", "tick": tick})
        tension_result = self.agent.tension_evaluator.evaluate_tension(
            scene_data["text"], writer_context
        )

        yield self._event("phase", {"name": "committing", "tick": tick})
        scene_id = self.agent.committer.commit_scene(scene_data, tick, plan)

        yield self._event("phase", {"name": "post_commit", "tick": tick})
        self.agent._save_qa(scene_id, tick, eval_result, plan)
        self.agent._verify_beat(scene_id, plan, current_beat, scene_data, tick=tick)
        self.agent._save_tension(scene_id, tension_result)

        yield self._event("phase", {"name": "memory", "tick": tick})
        self.agent._update_memory(scene_data["text"], scene_id, tick)

        yield self._event("phase", {"name": "finalizing", "tick": tick})
        self.agent._bump_loop_mentions(plan)
        self.agent._advance_threads(plan, scene_id, tick)
        self.agent._check_goal_promotion(tick)
        self.agent._maybe_audit_threads(tick)

        self.agent.state["current_tick"] += 1
        self.agent._save_state()
        self.agent._auto_checkpoint()

        result = self.agent._build_tick_result(
            tick, scene_id, scene_data, execution_results,
            eval_result, tension_result,
        )
        result["text"] = scene_data.get("text", "")[:8000]
        yield self._event("tick_complete", result)

    def _stream_first_tick(self, tick: int) -> Generator[str, None, None]:
        """Stream a first tick (tick 0) with two-phase entity generation."""
        agent = self.agent

        yield self._event("phase", {"name": "context", "tick": tick})
        context = agent.context_builder.build_planner_context(
            agent.state, notes=getattr(agent, '_tick_notes', ''),
        )

        yield self._event("phase", {"name": "planning", "tick": tick})
        plan = agent._generate_plan(context)
        from .schemas import validate_plan
        validate_plan(plan)

        # Phase 1: Generate entities only
        yield self._event("phase", {"name": "entity_generation", "tick": tick})
        entity_results = agent._execute_entity_generation_only(plan, tick)
        agent._update_plan_with_entity_ids(plan, entity_results)
        agent._set_active_char(entity_results, plan)

        # Phase 2: Execute remaining tools + write scene
        yield self._event("phase", {"name": "execution", "tick": tick})
        remaining_results = agent._execute_remaining_tools(plan, tick, entity_results)
        execution_results = agent._merge_execution_results(entity_results, remaining_results)
        agent.plan_manager.save_plan(tick, plan, execution_results, context)

        yield self._event("phase", {"name": "writing", "tick": tick})
        writer_context = agent.writer_context_builder.build_writer_context(
            plan, execution_results, agent.state,
            notes=getattr(agent, '_tick_notes', ''),
        )

        yield self._event("phase", {"name": "generating", "tick": tick})
        scene_data = agent.writer.write_scene(writer_context)

        yield self._event("phase", {"name": "evaluation", "tick": tick})
        eval_result = agent.evaluator.evaluate_scene(
            scene_data["text"], writer_context
        )
        if not eval_result["passed"] and eval_result.get("issues"):
            raise ValueError(f"Scene evaluation failed: {eval_result['issues']}")

        yield self._event("phase", {"name": "committing", "tick": tick})
        scene_id = agent.committer.commit_scene(scene_data, tick, plan)

        yield self._event("phase", {"name": "memory", "tick": tick})
        agent._update_memory(scene_data["text"], scene_id, tick)
        agent.vector.index_scene(
            agent.memory.load_scene(
                agent.memory.list_scenes()[-1]
            )
        )

        agent.state["current_tick"] += 1
        agent._save_state()

        result = {
            "success": True,
            "tick": tick,
            "scene_id": scene_id,
            "scene_file": f"scenes/scene_{tick:03d}.md",
            "word_count": scene_data.get("word_count", 0),
            "text": scene_data.get("text", "")[:8000],
        }
        yield self._event("tick_complete", result)

    @staticmethod
    def _event(event_type: str, data: dict) -> str:
        """Format an SSE event string."""
        return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
