"""Project manager - manage StoryAgent instance lifecycle."""

import time
import logging
from pathlib import Path
from typing import Any, Dict, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProjectInstance:
    """Project instance state."""
    project_id: str
    project_path: Path
    agent: Any
    created_at: float
    last_tick_at: float = 0
    tick_count: int = 0
    status: str = "idle"  # idle | running | paused | error
    error_message: str = ""


class ProjectManager:
    """Manage all active project instances.

    Responsibilities:
    - Create / load / unload projects
    - Maintain StoryAgent instance pool
    - Prevent duplicate initialization
    - Enforce resource limits
    """

    def __init__(self, llm_pool: 'LLMPool', config: dict):
        self.llm_pool = llm_pool
        self.config = config
        self.projects: Dict[str, ProjectInstance] = {}
        self.max_projects = config.get('daemon.max_concurrent_projects', 10)

    def get_or_create_project(self, project_path: str) -> ProjectInstance:
        """Get or create a project instance.

        If already loaded, returns cached instance.
        Otherwise creates a new StoryAgent.
        """
        from ..agent.agent import StoryAgent
        from ..tools.registry import ToolRegistry
        from ..tools.memory_tools import (
            MemorySearchTool, CharacterGenerateTool, LocationGenerateTool,
            RelationshipCreateTool, RelationshipUpdateTool, RelationshipQueryTool,
            FactionGenerateTool, FactionUpdateTool, FactionQueryTool
        )
        from ..tools.name_generator import NameGeneratorTool
        from ..memory.manager import MemoryManager
        from ..memory.vector_store import VectorStore

        path = Path(project_path)
        project_id = path.name

        if project_id in self.projects:
            return self.projects[project_id]

        if len(self.projects) >= self.max_projects:
            raise RuntimeError(f"Max projects ({self.max_projects}) reached")

        # Load project config
        from ..cli.project import get_project_config
        proj_config = get_project_config(path)

        # Get LLM connection
        backend = proj_config.get('llm.backend', 'codex')
        model = proj_config.get('llm.model', 'gpt-5.1')
        llm = self.llm_pool.get_connection(backend=backend, model=model)

        # Initialize components
        tool_registry = ToolRegistry()
        memory_manager = MemoryManager(path)
        vector_store = VectorStore(path)
        from ..configs.constants import DATA_NAMES_DIR
        data_dir = Path(__file__).parent.parent / DATA_NAMES_DIR
        name_gen_tool = NameGeneratorTool(data_dir)

        tool_registry.register(name_gen_tool)
        tool_registry.register(MemorySearchTool(memory_manager, vector_store))
        tool_registry.register(CharacterGenerateTool(memory_manager, vector_store, name_gen_tool.generator))
        tool_registry.register(LocationGenerateTool(memory_manager, vector_store))
        tool_registry.register(RelationshipCreateTool(memory_manager))
        tool_registry.register(RelationshipUpdateTool(memory_manager))
        tool_registry.register(RelationshipQueryTool(memory_manager))
        tool_registry.register(FactionGenerateTool(memory_manager, vector_store, name_gen_tool.generator))
        tool_registry.register(FactionUpdateTool(memory_manager, vector_store))
        tool_registry.register(FactionQueryTool(memory_manager, vector_store))

        cfg = proj_config.to_dict() if hasattr(proj_config, 'to_dict') else proj_config

        agent = StoryAgent(path, llm, tool_registry, cfg)

        instance = ProjectInstance(
            project_id=project_id,
            project_path=path,
            agent=agent,
            created_at=time.time()
        )
        self.projects[project_id] = instance
        logger.info("Created project instance: %s", project_id)
        return instance

    def remove_project(self, project_id: str):
        """Unload a project, freeing resources."""
        if project_id in self.projects:
            del self.projects[project_id]
            logger.info("Removed project instance: %s", project_id)

    def get_active_projects(self) -> List[Dict[str, Any]]:
        """Get info on all active projects."""
        return [
            {
                "project_id": p.project_id,
                "path": str(p.project_path),
                "last_tick_at": p.last_tick_at,
                "tick_count": p.tick_count,
                "status": p.status,
            }
            for p in self.projects.values()
        ]
