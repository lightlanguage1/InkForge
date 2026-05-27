"""共享依赖 — 引擎单例 + 项目路径解析 + agent 创建。"""

from pathlib import Path
from typing import Optional

from ..configs.config import Config
from ..engine.core import EngineCore
from ..cli.project import find_project_dir, get_project_config as load_config
from ..agent.factory import create_agent as _create_agent

_config = Config()
_engine: Optional[EngineCore] = None


def get_engine() -> EngineCore:
    global _engine
    if _engine is None:
        _engine = EngineCore(_config.to_dict())
    return _engine


def resolve_project(project_id: str) -> Path:
    return Path(find_project_dir(project_id))


def create_agent(project_dir: Path, llm_backend=None, llm_model=None, save_prompts=False):
    return _create_agent(
        project_dir, load_config(project_dir),
        llm_backend=llm_backend, llm_model=llm_model,
        save_prompts=save_prompts,
    )
