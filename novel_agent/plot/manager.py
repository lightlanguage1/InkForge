from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Dict, Any
import json
from datetime import datetime

from functools import lru_cache
from pathlib import Path as _Path

from ..configs.constants import DATA_TEMPLATES_DIR
from ..memory.manager import MemoryManager
from ..memory.entities import PlotBeat, PlotOutline

_TEMPLATE_DIR = _Path(__file__).resolve().parent.parent / DATA_TEMPLATES_DIR


@lru_cache(maxsize=2)
def _load_plot_template(name: str) -> str:
    path = _TEMPLATE_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def format_plot_generation_prompt(context: dict) -> str:
    template = _load_plot_template("plot_generation_prompt")
    for key, value in context.items():
        template = template.replace("{" + key + "}", str(value))
    template = template.replace("{{", "{").replace("}}", "}")
    return template


class PlotOutlineManager:
    """Manages the emergent plot outline (Phase 1, CLI-only).
    
    Stores beats in project_root/plot_outline.json
    """

    def __init__(self, project_dir: Path, llm_interface=None):
        self.project_dir = Path(project_dir)
        self.llm = llm_interface
        self.outline_file = self.project_dir / "plot_outline.json"
        self.memory = MemoryManager(self.project_dir)

    # ---------- Persistence ----------
    def load_outline(self) -> PlotOutline:
        if self.outline_file.exists():
            try:
                return PlotOutline.from_json(self.outline_file)
            except Exception:
                # Corrupt file; start fresh but keep backup
                backup = self.outline_file.with_suffix(".json.bak")
                self.outline_file.replace(backup)
        outline = PlotOutline(beats=[], created_at=self._now(), last_updated=self._now())
        return outline

    def save_outline(self, outline: PlotOutline) -> None:
        outline.last_updated = self._now()
        outline.to_json(self.outline_file)

    # ---------- ID helpers ----------
    def _next_id(self, existing_ids: List[str]) -> str:
        max_n = 0
        for bid in existing_ids:
            try:
                if bid.startswith("PB"):
                    n = int(bid[2:])
                    max_n = max(max_n, n)
            except ValueError:
                continue
        return f"PB{max_n+1:03d}"

    def _assign_ids(self, outline: PlotOutline, beats: List[PlotBeat]) -> List[PlotBeat]:
        existing_ids = [b.id for b in outline.beats if b.id]
        assigned: List[PlotBeat] = []
        for b in beats:
            if not b.id:
                b.id = self._next_id(existing_ids)
                existing_ids.append(b.id)
            if not b.created_at:
                b.created_at = self._now()
            assigned.append(b)
        return assigned

    # ---------- Generation ----------
    def generate_next_beats(self, count: int = 5) -> List[PlotBeat]:
        """Generate candidate beats from current story state via LLM.
        Returns beats without assigning IDs; call add_beats() to persist.
        """
        ctx = self._build_generation_context(count)
        prompt = format_plot_generation_prompt(ctx)
        # Use planner token budget as a safe default
        max_tokens = ctx.get("planner_max_tokens", 1000)
        response = self.llm.generate(prompt, max_tokens=max_tokens)
        beats = self._parse_beats_response(response)
        return beats

    def add_beats(self, beats: List[PlotBeat]) -> List[PlotBeat]:
        outline = self.load_outline()
        beats_assigned = self._assign_ids(outline, beats)
        outline.beats.extend(beats_assigned)
        self.save_outline(outline)
        return beats_assigned

    def get_next_beat(self) -> Optional[PlotBeat]:
        outline = self.load_outline()
        for b in outline.beats:
            if b.status == "pending":
                return b
        return None

    def validate_outline(self, outline: "PlotOutline") -> list:
        """Validate outline consistency. Returns list of issue strings.

        Currently a stub — returns empty list (no issues detected).
        Future: check beat dependencies, status transitions, etc.
        """
        return []

    # ---------- Utilities ----------
    def _build_generation_context(self, count: int) -> Dict[str, Any]:
        state = self._load_state()
        novel_name = state.get("novel_name", "Untitled Novel")
        current_tick = state.get("current_tick", 0)

        # Open loops
        loops = self.memory.load_open_loops()
        open_loops_desc = []
        for l in loops:
            if l.status == "open":
                line = f"{l.id}: ({l.importance}) {l.description}"
                open_loops_desc.append(line)
        open_loops_text = "\n".join(open_loops_desc) if open_loops_desc else "None"

        # Recent scenes (last 3)
        scene_ids = self.memory.list_scenes()
        scene_ids_sorted = sorted(scene_ids)
        recent_ids = scene_ids_sorted[-3:]
        recent_lines = []
        for sid in recent_ids:
            s = self.memory.load_scene(sid)
            if not s:
                continue
            summ = "; ".join(s.summary) if getattr(s, "summary", None) else ""
            recent_lines.append(f"{sid}: {s.title or ''} — {summ}")
        recent_text = "\n".join(recent_lines) if recent_lines else "None"

        # Story foundation (hard constraints from user)
        foundation = state.get("story_foundation", {})
        foundation_text = (
            f"类型：{foundation.get('genre', '')}\n"
            f"前提：{foundation.get('premise', '')}\n"
            f"主角：{foundation.get('protagonist_archetype', '')}\n"
            f"背景：{foundation.get('setting', '')}\n"
            f"基调：{foundation.get('tone', '')}\n"
            f"主题：{', '.join(foundation.get('themes', [])) if isinstance(foundation.get('themes'), list) else foundation.get('themes', '')}"
        )

        # Factions with stance info
        faction_ids = self.memory.list_factions()
        faction_lines = []
        if faction_ids:
            active_char_id = state.get("active_character", "")
            for fid in faction_ids:
                fac = self.memory.load_faction(fid)
                if not fac:
                    continue
                name = getattr(fac, 'name', fid)
                org_type = getattr(fac, 'org_type', 'other')
                summary = getattr(fac, 'summary', '')
                stance_map = getattr(fac, 'stance_by_character', {}) or {}
                # Show stance toward protagonist
                stance = stance_map.get(active_char_id, "unknown") if active_char_id else "unknown"
                faction_lines.append(
                    f"- {name} ({fid}) — 类型:{org_type} 对主角态度:{stance}\n"
                    f"  概述:{summary}"
                )
        factions_text = "\n".join(faction_lines) if faction_lines else "暂无势力设定"

        # World lore / rules
        lore_items = self.memory.load_all_lore()
        lore_lines = []
        for l in lore_items:
            imp = getattr(l, "importance", "normal") or "normal"
            content = getattr(l, "content", "")
            cat = getattr(l, "category", "其他")
            lore_lines.append(f"- [{imp}] [{cat}] {content}")
        lore_text = "\n".join(lore_lines) if lore_lines else "暂无世界观规则"

        return {
            "novel_name": novel_name,
            "current_tick": current_tick,
            "story_foundation": foundation_text,
            "open_loops": open_loops_text,
            "recent_scenes": recent_text,
            "factions": factions_text,
            "world_lore": lore_text,
            "count": count,
            "planner_max_tokens": 1000,
        }

    def _parse_beats_response(self, response: str) -> List[PlotBeat]:
        # Try JSON extraction - look for code blocks first
        import re
        
        # Try to extract from markdown code block
        code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.S)
        if code_block_match:
            json_str = code_block_match.group(1)
        else:
            # Try to find raw JSON object with beats array
            # Use greedy match to get the full JSON object
            match = re.search(r"\{\s*\"beats\"\s*:\s*\[.*\]\s*\}", response, re.S)
            json_str = match.group(0) if match else None
        
        data = None
        if json_str:
            try:
                data = json.loads(json_str)
            except Exception as e:
                print(f"        [WARN]  JSON parse error: {e}")
                data = None
        
        if not data:
            # Fallback: try to parse line-based bullets into descriptions
            lines = [ln.strip(" -\t") for ln in response.splitlines() if ln.strip()]
            # Filter out JSON syntax lines
            descs = [ln for ln in lines if ln and not ln.startswith("BEAT") 
                     and not ln.startswith("{") and not ln.startswith("}")
                     and not ln.startswith("[") and not ln.startswith("]")
                     and not ln.startswith('"beats"')]
            return [PlotBeat(id="", description=d) for d in descs[:5]]

        beats_data = data.get("beats", [])
        beats: List[PlotBeat] = []
        for b in beats_data:
            beats.append(
                PlotBeat(
                    id="",
                    description=b.get("description", ""),
                    characters_involved=b.get("characters_involved", []) or [],
                    location=b.get("location"),
                    plot_threads=b.get("plot_threads", []) or [],
                    tension_target=b.get("tension_target"),
                    prerequisites=b.get("prerequisites", []) or [],
                    resolves_loops=b.get("resolves_loops", []) or [],
                    creates_loops=b.get("creates_loops", []) or [],
                )
            )
        return beats

    def _load_state(self) -> Dict[str, Any]:
        state_path = self.project_dir / "state.json"
        try:
            with open(state_path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat() + "Z"
