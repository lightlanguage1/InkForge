"""Context builder for planner prompts."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List
from ..memory.manager import MemoryManager
from ..memory.vector_store import VectorStore
from ..plot.manager import PlotOutlineManager
from ..memory.entities import Character, Location, Scene, OpenLoop, PlotBeat
from ..tools.registry import ToolRegistry


@dataclass
class TickContext:
    """一次 tick 的全部上下文。一次构建，多处复用。"""
    tick: int
    novel_name: str
    foundation: dict
    active_char: Optional[Character] = None
    active_location: Optional[Location] = None
    recent_scenes: List[Scene] = field(default_factory=list)
    open_loops: List[OpenLoop] = field(default_factory=list)
    plot_beat: Optional[PlotBeat] = None
    tool_results: List[dict] = field(default_factory=list)
    qa_feedback: str = ""


class ContextBuilder:
    """Builds context for planner prompts.
    
    Gathers all necessary information from the story state and formats it
    for inclusion in the planner LLM prompt.
    """
    
    def __init__(
        self,
        memory_manager: MemoryManager,
        vector_store: VectorStore,
        tool_registry: ToolRegistry,
        config: dict
    ):
        """Initialize context builder.
        
        Args:
            memory_manager: Memory manager instance
            vector_store: Vector store instance
            tool_registry: Tool registry instance
            config: Project configuration
        """
        self.memory = memory_manager
        self.vector = vector_store
        self.tools = tool_registry
        self.config = config
        
        # Get configurable context settings
        self.recent_scenes_count = config.get('generation.recent_scenes_count', 3)
        self.include_overall_summary = config.get('generation.include_overall_summary', True)

    def build_tick_context(
        self,
        project_state: dict,
        current_beat: Optional[PlotBeat] = None,
    ) -> TickContext:
        """统一构建一次 tick 的全部上下文。"""
        tick = project_state.get("current_tick", 0)
        foundation = project_state.get("story_foundation", {})

        active_char_id = project_state.get("active_character", "")
        active_char = self.memory.load_character(active_char_id) if active_char_id else None
        active_loc_id = active_char.current_state.location_id if active_char else None
        active_loc = self.memory.load_location(active_loc_id) if active_loc_id else None

        return TickContext(
            tick=tick,
            novel_name=project_state.get("novel_name", "Untitled"),
            foundation=foundation,
            active_char=active_char,
            active_location=active_loc,
            recent_scenes=self._load_recent_scenes(tick),
            open_loops=self.memory.get_open_loops(),
            plot_beat=current_beat,
            qa_feedback=self._qa_feedback_text(),
        )

    def _load_recent_scenes(self, tick: int, count: int = 5) -> List[Scene]:
        """加载最近 N 个场景，最新的在前。"""
        scene_ids = self.memory.list_scenes()
        scenes = []
        for sid in reversed(scene_ids[-count:]):
            scene = self.memory.load_scene(sid)
            if scene:
                scenes.append(scene)
        return scenes

    def _qa_feedback_text(self) -> str:
        """加载最近 QA 反馈 — 包含上一幕的全部问题与警告。"""
        try:
            recent = self.memory.get_recent_scene_qa(count=3)
        except Exception:
            return ""
        if not recent:
            return ""
        lines = []
        for entry in recent:
            scene_id = entry.get("scene_id", "?")
            tick_num = entry.get("tick", None)
            evaluation = entry.get("evaluation", {})
            achieved = evaluation.get("achieved_change", {})
            achieved_val = achieved.get("value")
            prefix = f"Tick {tick_num} ({scene_id})" if tick_num is not None else f"Scene {scene_id}"
            lines.append(f"- {prefix}: change={'yes' if achieved_val else 'no' if achieved_val is not None else 'unknown'}")

            # Include full issues/warnings so Planner knows what went wrong last time
            issues = evaluation.get("issues", []) or []
            warnings = evaluation.get("warnings", []) or []
            if issues or warnings:
                for issue in issues:
                    lines.append(f"问题: {issue}")
                for warn in warnings:
                    lines.append(f"建议: {warn}")
        return "\n".join(lines)

    def build_planner_context(self, project_state: dict, current_beat=None, notes: str = "", rejection_feedback: str = "") -> dict:
        """Build context dictionary for planner prompt.

        Args:
            project_state: Current project state from state.json
            current_beat: Optional PlotBeat to execute in this tick
            notes: Per-tick direction notes (CLI --notes flag)
            rejection_feedback: Feedback from a rejected plan for retry
        """
        foundation = project_state.get("story_foundation", {})
        foundation_summary = (
            f"Genre: {foundation.get('genre', '')}\n"
            f"Premise: {foundation.get('premise', '')}\n"
            f"Protagonist: {foundation.get('protagonist_archetype', '')}\n"
            f"Setting: {foundation.get('setting', '')}\n"
            f"Tone: {foundation.get('tone', '')}"
        )
        context = {
            "novel_name": project_state.get("novel_name", "Untitled"),
            "current_tick": project_state.get("current_tick", 0),
            "active_character_id": project_state.get("active_character", ""),
            "active_character_name": "Unknown",
            "active_character_details": "No active character set.",
            "character_relationships": "No relationships yet.",
            "story_foundation_summary": foundation_summary,
            "pov_candidates": "",
            "pov_history": "",
        }
        
        # Load active character
        if context["active_character_id"]:
            char = self.memory.load_character(context["active_character_id"])
            if char:
                context["active_character_name"] = char.name
                context["active_character_details"] = self._format_character(char)
                context["character_relationships"] = self._format_relationships(
                    context["active_character_id"]
                )
        
        # Get overall summary (if enabled) and recent scenes
        if self.include_overall_summary:
            context["overall_summary"] = self._get_overall_summary()
        else:
            context["overall_summary"] = ""
        
        context["recent_scenes_summary"] = self._get_recent_scenes_summary(
            self.recent_scenes_count
        )
        
        # Get open loops (filtered by active character relevance)
        context["open_loops_list"] = self._format_open_loops(
            pov_character_id=context["active_character_id"]
        )
        
        # Get tension history (Phase 7A.3)
        context["tension_history"] = self._get_tension_history()
        
        # Get factions summary (organizations relevant to the story)
        context["factions_summary"] = self._format_factions()
        
        # Relevant lore (filtered by scene keywords, top 5)
        context["relevant_lore"] = self._format_relevant_lore()

        # Get available tools description
        context["available_tools_description"] = self.tools.get_tools_description()

        # QA feedback (last tick summary + recent history)
        context["qa_feedback"] = self._get_qa_summary() + "\n" + self._get_qa_feedback()

        # List all existing characters so planner doesn't recreate them
        context["existing_characters_summary"] = self._format_all_characters()

        # Next plot beat - use passed beat if available, otherwise query
        if current_beat:
            beat_id = getattr(current_beat, "id", "") or ""
            description = getattr(current_beat, "description", "") or ""
            if beat_id and description:
                context["next_plot_beat"] = f"{beat_id}: {description}"
            else:
                context["next_plot_beat"] = description or "None"
            # Store beat object for multi-stage planner (internal use)
            context["_current_beat"] = current_beat
        else:
            context["next_plot_beat"] = self._get_next_plot_beat_hint(project_state)
            context["_current_beat"] = None
        
        # Beat enforcement instructions based on config
        context["beat_enforcement_instructions"] = self._get_beat_enforcement_instructions()

        # Multi-POV support
        context["pov_candidates"] = self._format_pov_candidates()
        context["pov_history"] = self._format_pov_history()

        # Character lifecycle
        context["absent_characters"] = self._format_absent_characters()

        # Thread dashboard (plot-line tracking)
        context["thread_dashboard"] = self._format_thread_dashboard(project_state.get("current_tick", 0))

        # Per-tick notes override config-level writer_notes
        context["writer_notes"] = self._format_writer_notes(notes)

        # Plan rejection feedback (retry loop)
        if rejection_feedback:
            context["plan_rejection_feedback"] = (
                f"**上一版计划被拒绝：** {rejection_feedback}\n\n"
                "请重新制定计划，解决上述问题。"
            )
        else:
            context["plan_rejection_feedback"] = ""

        return context

    def _format_writer_notes(self, per_tick_notes: str = "") -> str:
        """Format direction notes for planner/writer contexts.

        Per-tick notes (from CLI --notes) take precedence over the
        project-level ``generation.writer_notes`` config value.

        Includes a continuity guard so scene steering doesn't break
        character consistency or plot coherence.
        """
        notes = per_tick_notes.strip() if per_tick_notes else self.config.get('generation.writer_notes', '')
        if not notes:
            return ''
        return (
            '\n## 场景方向指导（必须执行）\n\n' + notes +
            '\n\n以上是用户指定的场景方向，请严格据此规划本章内容。'
            '在满足用户方向的前提下，保持故事连续性和角色性格一致。'
        )

    def _get_next_plot_beat_hint(self, project_state: dict) -> str:
        """Get a formatted hint for the next pending plot beat, if available.

        This is a soft integration: it simply exposes the next pending beat's
        ID and description as a hint to the planner. The planner remains free
        to deviate if following the beat would clearly break story constraints.
        """
        try:
            manager = PlotOutlineManager(self.memory.project_path)
        except Exception:
            return ""

        try:
            next_beat = manager.get_next_beat()
        except Exception:
            return ""

        if not next_beat:
            return "None (no pending beats in outline.)"

        beat_id = getattr(next_beat, "id", "") or ""
        description = getattr(next_beat, "description", "") or ""

        if beat_id and description:
            return f"{beat_id}: {description}"
        return description or ""
    
    def _format_character(self, character) -> str:
        """Format character details for prompt.
        
        Args:
            character: Character entity
        
        Returns:
            Formatted character description
        """
        parts = [
            f"Name: {character.name}",
            f"Role: {character.role}",
            f"Description: {character.description}",
        ]
        
        if character.current_state.goals:
            parts.append(f"Current Goals: {', '.join(character.current_state.goals)}")
        
        if character.current_state.emotional_state:
            parts.append(f"情绪状态: {character.current_state.emotional_state}")
        if character.current_state.emotion and character.current_state.emotion.dominant:
            parts.append(f"情绪维度: 效价={character.current_state.emotion.valence:.1f}, 唤醒度={character.current_state.emotion.arousal:.1f}")
        
        if character.current_state.location_id:
            parts.append(f"Current Location: {character.current_state.location_id}")
        
        return "\n".join(parts)

    def _format_pov_candidates(self) -> str:
        """List characters eligible for POV duty."""
        char_ids = self.memory.list_characters()
        candidates = []
        for cid in char_ids:
            char = self.memory.load_character(cid)
            if char and char.role in ("protagonist", "supporting"):
                pov_count = getattr(char, "pov_count", 0)
                candidates.append(f"  {cid} | {char.display_name} | {char.role} | POV次数={pov_count}")
        if not candidates:
            return "暂无可用POV候选角色。"
        return "\n".join(candidates)

    def _format_pov_history(self) -> str:
        """Show the POV character for each recent scene."""
        scene_ids = self.memory.list_scenes()
        if not scene_ids:
            return "暂无POV历史。"
        lines = []
        for sid in scene_ids[-8:]:  # last 8 scenes
            scene = self.memory.load_scene(sid)
            if scene:
                pov_id = getattr(scene, "pov_character_id", "") or ""
                tick = getattr(scene, "tick", "?")
                if pov_id:
                    char = self.memory.load_character(pov_id)
                    name = char.display_name if char else pov_id
                    lines.append(f"  S{tick:03d}: {name} ({pov_id})")
                else:
                    lines.append(f"  S{tick:03d}: 未知")
        if not lines:
            return "暂无POV历史。"
        return "\n".join(lines)

    def _format_all_characters(self) -> str:
        """Character roster — only active/returning + 1 absent suggestion.

        Hides sidelined/departed/deceased to keep the planner focused.
        """
        char_ids = self.memory.list_characters()
        if not char_ids:
            return "No characters exist yet."

        status_labels = {
            "active": "活跃", "sidelined": "暂离", "departed": "已离场",
            "deceased": "已故", "returning": "回归中",
        }

        shown = []
        absent_candidates = []

        for cid in char_ids:
            char = self.memory.load_character(cid)
            if not char:
                continue
            status = getattr(char, "status", "active") or "active"
            if status in ("active", "returning"):
                shown.append(char)
            elif status == "sidelined":
                absent_candidates.append(char)

        # Pick the most promising absent character (most prior appearances)
        absent_candidates.sort(key=lambda c: len(getattr(c, "appearance_ticks", []) or []), reverse=True)
        if absent_candidates:
            shown.append(absent_candidates[0])

        lines = ["### 角色登场表", ""]
        for char in shown:
            name = char.display_name or char.name
            role = char.role or "?"
            status = getattr(char, "status", "active") or "active"
            label = status_labels.get(status, status)
            last_tick = getattr(char, "last_scene_tick", -1)
            appearances = getattr(char, "appearance_ticks", []) or []
            count = len(appearances)
            note = getattr(char, "off_screen_note", "") or ""
            parts = [f"**{char.id} {name}** | {role} | {label} | 出场{count}次"]
            if last_tick >= 0:
                parts.append(f"| 最后:S{last_tick:03d}")
            if note:
                parts.append(f"| {note}")
            lines.append("  " + " ".join(parts))

        total = len(char_ids)
        shown_count = len(shown)
        if total > shown_count:
            lines.append(f"\n（全量{total}个角色，已隐藏{total - shown_count}个离场/已故/暂离角色）")

        return "\n".join(lines)

    def _format_relevant_lore(self) -> str:
        """Show top 5 lore items relevant to recent scenes (via ChromaDB).

        Falls back to showing the 5 most recently added lore items if
        ChromaDB has no results.
        """
        try:
            recent_ids = self.memory.list_scenes()
            if not recent_ids or len(recent_ids) < 1:
                return ""
            last_scene = self.memory.load_scene(recent_ids[-1])
            if not last_scene or not last_scene.summary:
                return ""
            query = " ".join(last_scene.summary) if isinstance(last_scene.summary, list) else str(last_scene.summary)
            results = self.vector.search_lore(query, n_results=5)
        except Exception:
            results = []

        if not results:
            return ""

        lines = ["### 相关世界观", ""]
        for r in results:
            doc = r.get("document", "") or r.get("text", "") or ""
            if doc:
                lines.append(f"- {doc[:200]}")
        return "\n".join(lines) if len(lines) > 2 else ""

    def _get_qa_summary(self) -> str:
        """Return a one-line summary of the last scene's QA metrics."""
        try:
            recent = self.memory.get_recent_scene_qa(count=1)
        except Exception:
            return ""
        if not recent:
            return ""
        entry = recent[0]
        ev = entry.get("evaluation", {}) or {}
        mode = ev.get("mode_used", "?")
        dialogue = ev.get("dialogue_count", "?")
        novelty = ev.get("novelty_score", "?")
        beat = (ev.get("beat_hint_alignment", {}) or {}).get("label", "?")
        return (
            f"**上轮QA:** 模式={mode} 对话={dialogue}轮 "
            f"新颖度={novelty} 节拍对齐={beat}"
        )

    def _format_absent_characters(self) -> str:
        """List characters missing for 5+ chapters — candidates for return."""
        char_ids = self.memory.list_characters()
        if not char_ids:
            return ""
        max_tick = 0
        scene_ids = self.memory.list_scenes()
        if scene_ids:
            last_scene = self.memory.load_scene(scene_ids[-1])
            if last_scene:
                max_tick = getattr(last_scene, "tick", 0)
        absent = []
        for cid in char_ids:
            char = self.memory.load_character(cid)
            if not char:
                continue
            status = getattr(char, "status", "active") or "active"
            if status in ("deceased", "departed"):
                continue
            last_tick = getattr(char, "last_scene_tick", -1)
            if last_tick < 0 or max_tick - last_tick < 5:
                continue
            name = char.display_name or char.name
            gap = max_tick - last_tick
            note = getattr(char, "off_screen_note", "") or ""
            absent.append((gap, cid, name, note))
        if not absent:
            return ""
        absent.sort(key=lambda x: -x[0])
        lines = ["### 缺席角色（超过5章未出场）", ""]
        for gap, cid, name, note in absent:
            line = f"- **{cid} {name}**: {gap}章未出场"
            if note:
                line += f"（{note}）"
            lines.append(line)
        lines.append("")
        lines.append("考虑本章是否适合让其中某个角色回归。")
        return "\n".join(lines)

    def _format_thread_dashboard(self, current_tick: int) -> str:
        from ..memory.thread_manager import ThreadManager
        mgr = ThreadManager(self.memory)
        return mgr.format_dashboard(current_tick)

    def _get_overall_summary(self) -> str:
        """Get high-level summary of all scenes so far.
        
        Returns:
            Formatted overall story summary
        """
        scene_ids = self.memory.list_scenes()
        
        if not scene_ids:
            return "Story has not yet begun."
        
        # Get all scene summaries
        all_summaries = []
        for scene_id in scene_ids:
            scene = self.memory.load_scene(scene_id)
            if scene and scene.summary:
                # Take first bullet point from each scene as high-level summary
                first_bullet = scene.summary[0] if scene.summary else "Scene generated"
                all_summaries.append(f"Tick {scene.tick}: {first_bullet}")
        
        if not all_summaries:
            return f"{len(scene_ids)} scenes generated so far."
        
        summary_text = "\n".join(all_summaries)
        return f"**Story So Far** ({len(scene_ids)} scenes):\n{summary_text}"
    
    def _get_recent_scenes_summary(self, count: int) -> str:
        """Get detailed summaries of recent scenes.
        
        Args:
            count: Number of recent scenes to include
        
        Returns:
            Formatted recent scenes summary
        """
        scene_ids = self.memory.list_scenes()
        
        if not scene_ids:
            return "No scenes yet."
        
        recent_ids = scene_ids[-count:] if len(scene_ids) >= count else scene_ids
        
        summaries = []
        for scene_id in recent_ids:
            scene = self.memory.load_scene(scene_id)
            if scene and scene.summary:
                summary_text = "\n  - ".join(scene.summary)
                title = scene.title if hasattr(scene, 'title') and scene.title else f"Scene {scene_id}"
                summaries.append(f"**{title}** (Tick {scene.tick}):\n  - {summary_text}")
        
        if not summaries:
            return f"Last {len(recent_ids)} scenes have no summaries."
        
        return "\n\n".join(summaries)
    
    def _format_open_loops(self, pov_character_id: str = "") -> str:
        """Format open loops, filtered by POV character relevance first.

        Only the top 10 loops (by relevance + importance) are shown
        to keep the planner focused on what matters for this scene.
        """
        open_loops = self.memory.get_open_loops()
        if not open_loops:
            return "No open loops."

        importance_weight = {"critical": 4, "high": 3, "medium": 2, "low": 1}

        def relevance_score(loop):
            score = importance_weight.get(loop.importance, 1)
            if pov_character_id and pov_character_id in (loop.related_characters or []):
                score += 3
            if loop.status == "urgent":
                score += 2
            return score

        sorted_loops = sorted(open_loops, key=relevance_score, reverse=True)
        shown = sorted_loops[:10]

        loop_lines = []
        for loop in shown:
            marker = "[急]" if loop.status == "urgent" else ""
            loop_lines.append(
                f"{marker} **{loop.id}** ({loop.importance}): {loop.description}"
            )

        if len(open_loops) > 10:
            loop_lines.append(f"\n（还有 {len(open_loops) - 10} 条线索未显示）")

        return "\n".join(loop_lines)
    
    def _format_relationships(self, character_id: str) -> str:
        """Format character relationships for prompt.
        
        Args:
            character_id: Character ID to get relationships for
        
        Returns:
            Formatted relationships description
        """
        relationships = self.memory.get_character_relationships(character_id)
        
        if not relationships:
            return f"Character {character_id} has no established relationships yet."
        
        rel_lines = []
        for rel in relationships:
            other_id = rel.get_other_character(character_id)
            other_char = self.memory.load_character(other_id)
            other_name = other_char.name if other_char else other_id
            
            perspective = rel.get_perspective(character_id)
            rel_type = rel.relationship_type
            status = rel.status
            
            rel_lines.append(
                f"- **{other_name}** ({other_id}): {rel_type} - {status}\n"
                f"  Perspective: \"{perspective}\""
            )
        
        return "\n".join(rel_lines)
    
    def _get_tension_history(self) -> str:
        """Get recent tension history for context (Phase 7A.3).
        
        Returns:
            Formatted tension history string with pacing suggestions
        """
        # Handle both Config object and plain dict
        if isinstance(self.config, dict) and 'generation' in self.config:
            enabled = self.config.get('generation', {}).get('enable_tension_tracking', True)
        else:
            enabled = self.config.get('generation.enable_tension_tracking', True)
        
        if not enabled:
            return ""
        
        # Get recent scene IDs
        scene_ids = self.memory.list_scenes()
        if not scene_ids:
            return ""
        
        # Get last 5 scene IDs
        recent_ids = scene_ids[-5:]
        
        # Load scenes and filter for tension data
        tension_scenes = []
        for scene_id in recent_ids:
            scene = self.memory.load_scene(scene_id)
            if scene and hasattr(scene, 'tension_level') and scene.tension_level is not None:
                tension_scenes.append(scene)
        
        if not tension_scenes:
            return ""
        
        # Format tension progression
        levels = [s.tension_level for s in tension_scenes]
        categories = [s.tension_category for s in tension_scenes]
        
        progression = ' → '.join(categories)
        levels_str = ', '.join(str(l) for l in levels)
        
        # Analyze pattern for gentle guidance
        result = f"Recent tension: [{levels_str}] ({progression})\n"
        
        # Add contextual pacing notes (informational, not prescriptive)
        if len(levels) >= 3:
            avg_tension = sum(levels) / len(levels)
            variance = max(levels) - min(levels)
            
            # Check for sustained high tension (priority check)
            if avg_tension >= 7 and all(l >= 6 for l in levels[-3:]):
                result += "\nNote: Tension has been high. Consider whether a brief respite would:\n"
                result += "  - Allow character reflection and emotional processing\n"
                result += "  - Build anticipation for the next major event\n"
                result += "  - Provide contrast to make future tension more impactful\n"
            
            # Check for sustained low tension (priority check)
            elif avg_tension <= 3 and all(l <= 4 for l in levels[-3:]):
                result += "\nNote: Tension has been low. Consider whether the story needs:\n"
                result += "  - Rising stakes or complications\n"
                result += "  - Introduction of conflict or obstacles\n"
                result += "  - Continued calm (if building toward something)\n"
            
            # Check for flatness (low variance) - only if not already caught above
            elif variance <= 1 and len(levels) >= 4:
                result += "\nNote: Tension has been steady. Consider whether the story would benefit from:\n"
                result += "  - A calm moment (reflection, planning, character interaction)\n"
                result += "  - A tension spike (revelation, confrontation, danger)\n"
                result += "  - Continued current pacing (if appropriate for the narrative)\n"
        
        result += "\nThis is informational only - follow the natural story flow."
        
        return result

    def _get_qa_feedback(self) -> str:
        try:
            recent = self.memory.get_recent_scene_qa(count=3)
        except Exception:
            return ""
        if not recent:
            return ""
        lines = []
        for entry in recent:
            scene_id = entry.get("scene_id", "?")
            tick = entry.get("tick", None)
            evaluation = entry.get("evaluation", {})
            achieved = evaluation.get("achieved_change", {})
            achieved_val = achieved.get("value")
            achieved_label = "yes" if achieved_val else "no" if achieved_val is not None else "unknown"
            mode_used = evaluation.get("mode_used", "unknown")
            dialogue_count = evaluation.get("dialogue_count", None)
            novelty = evaluation.get("novelty_score", None)
            beat_align = evaluation.get("beat_hint_alignment", {}) or {}
            beat_align_label = beat_align.get("label")
            beat_align_score = beat_align.get("score")
            warnings = evaluation.get("warnings", [])
            prefix = f"Tick {tick} ({scene_id})" if tick is not None else f"Scene {scene_id}"
            summary_parts = [f"change={achieved_label}", f"mode={mode_used}"]
            if dialogue_count is not None:
                summary_parts.append(f"dialogue={dialogue_count}")
            if novelty is not None:
                summary_parts.append(f"novelty={novelty}")
            if beat_align_label:
                if isinstance(beat_align_score, (int, float)):
                    summary_parts.append(f"beat_align={beat_align_label}({beat_align_score:.2f})")
                else:
                    summary_parts.append(f"beat_align={beat_align_label}")
            line = f"- {prefix}: " + ", ".join(summary_parts)
            if warnings:
                joined = "; ".join(warnings[:3])
                line += f"\n  Warnings: {joined}"
            lines.append(line)
        return "\n".join(lines)

    def _format_factions(self) -> str:
        """Format factions (organizations) for prompt context.
        
        Returns:
            Formatted list of factions by importance
        """
        # Access MemoryManager directly
        try:
            faction_ids = self.memory.list_factions()
        except Exception:
            return "No factions."
        if not faction_ids:
            return "No factions."
        factions = []
        for fid in faction_ids:
            fac = self.memory.load_faction(fid)
            if fac:
                factions.append(fac)
        # Sort by importance
        importance_order = {"critical": 3, "high": 2, "medium": 1, "low": 0}
        factions.sort(key=lambda f: importance_order.get(getattr(f, 'importance', 'medium'), 1), reverse=True)
        lines = []
        for f in factions[:8]:
            imp = getattr(f, 'importance', 'medium')
            org_type = getattr(f, 'org_type', 'other')
            name = getattr(f, 'name', f.id)
            summary = getattr(f, 'summary', '')
            lines.append(f"- {name} ({f.id}) — type: {org_type}, importance: {imp}. {summary}")
        return "\n".join(lines)
    
    def _get_beat_enforcement_instructions(self) -> str:
        """Generate beat enforcement instructions based on plot-first config.
        
        Returns:
            Instructions for how to handle the plot beat
        """
        use_plot_first = self.config.get('generation.use_plot_first', True)

        if not use_plot_first:
            return ""
        
        allow_beat_skip = self.config.get('generation.allow_beat_skip', False)
        fallback_to_reactive = self.config.get('generation.fallback_to_reactive', True)
        
        if not allow_beat_skip and not fallback_to_reactive:
            # STRICT MODE - Beat is REQUIRED
            return """**[WARN] CRITICAL REQUIREMENT - STRICT PLOT-FIRST MODE [WARN]**

The plot beat shown above is MANDATORY and MUST be executed in this scene.

You MUST:
- Set `beat_target.beat_id` to the beat's ID shown above
- Set `strategy` to `"direct"` 
- Create a plan that will ACCOMPLISH this beat in this scene
- The scene prose MUST show this beat happening

You CANNOT:
- Skip this beat (strategy="skip" is FORBIDDEN)
- Defer this beat to a future scene
- Only set up or follow up the beat - it must be EXECUTED NOW

If you believe the beat cannot be accomplished due to story constraints, you must still attempt it.
The beat verification system will check if you succeeded."""
        
        elif allow_beat_skip and not fallback_to_reactive:
            # STANDARD MODE - Beat should be attempted, can be skipped with justification
            return """**Plot-First Mode: Standard Enforcement**

If a Next Plot Beat is shown above, you should strongly prefer to execute it:

- **PREFERRED**: Set `beat_target.beat_id` to the beat's ID and `strategy` to `"direct"` to execute it
- If you need to set up the beat first, use `strategy` = `"setup"` and explain in `notes`
- If you must skip this beat, set `beat_target.beat_id` to `null`, `strategy` to `"skip"`, and provide a strong justification in `notes`

Skipping should be rare and only for compelling story reasons (e.g., critical character development, pacing emergency).

Do not invent beat IDs. Only use the ID shown in Next Plot Beat, or null."""
        
        else:
            # LENIENT MODE - Beat is a hint, can fall back to reactive
            return """**Plot-First Mode: Lenient (Hint-Based)**

If a Next Plot Beat is shown above, you may choose how to relate to it:

- If this scene will EXECUTE that beat, set `beat_target.beat_id` to that beat's ID and `strategy` to `"direct"`
- If this scene will SET UP or FOLLOW UP that beat, use `strategy` = `"setup"` or `"followup"`
- If you decide this scene should NOT focus on that beat, set `beat_target.beat_id` to `null`, `strategy` to `"skip"`, and explain in `notes`

The beat is a suggestion to maintain forward momentum. You may deviate if story needs require it.

Do not invent beat IDs. Only use the ID shown in Next Plot Beat, or null."""
