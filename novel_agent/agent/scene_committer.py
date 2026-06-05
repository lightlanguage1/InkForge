"""Scene committer for saving scenes to disk and memory."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

from novel_agent.memory.entities import Scene


def strip_markdown(text: str) -> str:
    """Remove common markdown artifacts from LLM-generated prose."""
    # Remove bold markers (but keep the text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    # Remove italic markers
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # Remove inline code
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Remove heading markers (###, ##, # at line start)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r'^-{3,}\s*$', '', text, flags=re.MULTILINE)
    # Remove strikethrough
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    # Remove blockquote markers
    text = re.sub(r'^>\s?', '', text, flags=re.MULTILINE)
    # Clean up excess whitespace from removals
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    return text.strip()


class SceneCommitter:
    """Commits scenes to disk and memory systems."""
    
    def __init__(self, memory_manager, vector_store, summarizer, project_path):
        """Initialize scene committer.
        
        Args:
            memory_manager: MemoryManager instance
            vector_store: VectorStore instance
            summarizer: SceneSummarizer instance
            project_path: Path to project directory
        """
        self.memory = memory_manager
        self.vector = vector_store
        self.summarizer = summarizer
        self.project_path = Path(project_path)
        self.scenes_dir = self.project_path / "scenes"
    
    def commit_scene(
        self,
        scene_data: Dict[str, Any],
        tick: int,
        plan: Dict[str, Any]
    ) -> str:
        """Commit scene to disk and memory.
        
        Args:
            scene_data: From SceneWriter (text, word_count, title)
            tick: Current tick number
            plan: Original plan from planner
        
        Returns:
            Scene ID
        """
        # 1. Generate scene ID
        scene_id = self.memory.generate_id("scene")
        
        # 2. Save markdown file
        markdown_file = self._save_markdown(
            scene_id,
            scene_data["text"],
            scene_data["title"],
            tick
        )
        
        # 3. Generate summary
        summary = self.summarizer.summarize_scene(
            scene_data["text"],
            max_bullets=5
        )
        
        # 4. Extract characters from plan
        characters_present = self._extract_characters(plan)
        
        # 5. Create Scene entity
        scene = Scene(
            id=scene_id,
            tick=tick,
            title=scene_data["title"],
            pov_character_id=plan.get("pov_character", ""),
            location_id=plan.get("target_location", ""),
            markdown_file=str(markdown_file.relative_to(self.project_path)),
            word_count=scene_data["word_count"],
            summary=summary,
            characters_present=characters_present,
            key_events=[],  # Could extract from summary in future
            metadata={"plan_rationale": plan.get("rationale", "")}
        )
        
        # 6. Save scene metadata
        self.memory.save_scene(scene)
        
        # 7. Index in vector database
        self.vector.index_scene(scene)

        # 8. 分支指针前移（git commit）
        from ..memory.branch_manager import advance_branch
        advance_branch(self.memory.project_path)

        return scene_id
    
    def _save_markdown(
        self,
        scene_id: str,
        text: str,
        title: str,
        tick: int
    ) -> Path:
        """Save scene text to markdown file.

        如果该 tick 的旧场景文件已存在（回滚后重写），
        自动将旧文件归档带时间戳后缀，不丢失历史节点。
        """
        self.scenes_dir.mkdir(parents=True, exist_ok=True)

        filename = f"scene_{tick:03d}.md"
        filepath = self.scenes_dir / filename

        # 回滚后重写：旧文件归档，不覆盖（git 模型）
        if filepath.exists():
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            archived = self.scenes_dir / f"scene_{tick:03d}.md.{ts}.bak"
            filepath.rename(archived)
            logger.info("归档旧场景: %s → %s", filename, archived.name)

        cleaned_text = strip_markdown(text)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# 第{tick+1}章 {title}\n\n")
            f.write(cleaned_text)
            f.write("\n")

        return filepath
    
    def _extract_characters(self, plan: Dict[str, Any]) -> List[str]:
        """Extract character IDs present in this scene from plan metadata."""
        characters = set()

        # 1. POV character
        pov_char = plan.get("pov_character")
        if pov_char and pov_char.startswith("C"):
            characters.add(pov_char)

        # 2. Beat characters_involved
        beat_target = plan.get("beat_target") or {}
        if isinstance(beat_target, dict):
            beat_id = beat_target.get("beat_id")
            if beat_id:
                try:
                    from ..plot.manager import PlotOutlineManager
                    mgr = PlotOutlineManager(self.project_path)
                    outline = mgr.load_outline()
                    beat = next((b for b in outline.beats if b.id == beat_id), None)
                    if beat and getattr(beat, "characters_involved", None):
                        for cid in beat.characters_involved:
                            if cid.startswith("C"):
                                characters.add(cid)
                except Exception:
                    pass

        return list(characters)
