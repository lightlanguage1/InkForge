"""Engine Core — persistent engine runtime."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class EngineCore:
    """InkForge persistent engine core.

    Manages LLM connection pool, project instances, and skill store lifecycle.
    """

    def __init__(self, config: dict):
        self.config = config

        from ..tools.llm_pool import LLMPool
        self.llm_pool = LLMPool(config)

        from .project_manager import ProjectManager
        self.project_manager = ProjectManager(self.llm_pool, config)

        # Skill store (lazy initialized on first access)
        self._skill_store = None

        logger.info("Engine Core initialized")

    def create_project(self, name: str, directory: str = None,
                       **foundation_kwargs) -> str:
        """Create a new novel project."""
        from ..cli.project import create_novel_project
        from ..cli.foundation import StoryFoundation

        foundation = None
        if any([foundation_kwargs.get('genre'), foundation_kwargs.get('premise')]):
            themes_raw = foundation_kwargs.get('themes', '')
            themes_list = [t.strip() for t in str(themes_raw).split(',') if t.strip()] if themes_raw else []
            foundation = StoryFoundation(
                genre=foundation_kwargs.get('genre', ''),
                premise=foundation_kwargs.get('premise', ''),
                protagonist_archetype=foundation_kwargs.get('protagonist', ''),
                setting=foundation_kwargs.get('setting', ''),
                tone=foundation_kwargs.get('tone', ''),
                themes=themes_list,
                primary_goal=foundation_kwargs.get('primary_goal', ''),
            )

        project_dir = create_novel_project(
            name=name,
            base_dir=directory,
            foundation=foundation,
        )
        return str(project_dir)

    @property
    def skill_store(self):
        """Lazy-initialized SkillStore instance."""
        if self._skill_store is None:
            from ..skill.store import SkillStore
            self._skill_store = SkillStore(self.config)
        return self._skill_store

    def shutdown(self):
        """Gracefully shut down the engine."""
        self.project_manager.projects.clear()
        logger.info("Engine Core shutdown complete")
