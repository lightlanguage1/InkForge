"""共享依赖 — 引擎单例 + 项目路径解析 + agent 创建 + 生成锁。"""

import logging
from pathlib import Path
from typing import Optional

from ..configs.config import Config
from ..engine.core import EngineCore
from ..cli.project import find_project_dir, get_project_config as _load_config
from ..agent.factory import create_agent as _create_agent

logger = logging.getLogger(__name__)

_config = Config()
_engine: Optional[EngineCore] = None

# —— 生成锁（同一项目同一时间只能有一个生成/改写操作）——
_active_generations: set[str] = set()


def _lock_key(project_id: str) -> str:
    from ..user.context import get_current_user
    return f"{get_current_user()}:{project_id}"


def try_lock_generation(project_id: str) -> bool:
    """获取生成锁。返回 False 表示已有操作在进行中。"""
    key = _lock_key(project_id)
    if key in _active_generations:
        return False
    _active_generations.add(key)
    return True


def release_generation(project_id: str):
    """释放生成锁。"""
    _active_generations.discard(_lock_key(project_id))


def is_generation_running(project_id: str) -> bool:
    """检查是否有生成操作正在进行。"""
    return _lock_key(project_id) in _active_generations


def get_engine() -> EngineCore:
    global _engine
    if _engine is None:
        _engine = EngineCore(_config.to_dict())
    return _engine


def get_novels_dir() -> Path:
    """Return the user-scoped novels directory based on auth context."""
    from ..user.context import get_current_user
    user_id = get_current_user()
    novels = (Path("work/users") / user_id / "novels").resolve()
    novels.mkdir(parents=True, exist_ok=True)
    return novels


def _scan_dir_for_project(base: Path, project_id: str) -> Path | None:
    """Scan *base* for a subdirectory whose name contains *project_id*."""
    if not base.exists():
        return None
    direct = base / project_id
    if direct.is_dir() and (direct / "state.json").exists():
        return direct.resolve()
    for entry in base.iterdir():
        if entry.is_dir() and project_id in entry.name:
            state = entry / "state.json"
            if state.exists():
                return entry.resolve()
    return None


def resolve_project(project_id: str) -> Path:
    """Resolve project_id to a project directory with state.json."""
    as_path = Path(project_id)
    if as_path.is_absolute() and (as_path / "state.json").exists():
        return as_path.resolve()

    found = _scan_dir_for_project(get_novels_dir(), project_id)
    if found:
        return found

    raise ValueError(f"未找到项目: {project_id}")


def create_agent(project_dir: Path, llm_backend=None, llm_model=None, save_prompts=False):
    return _create_agent(
        project_dir, _load_config(project_dir),
        llm_backend=llm_backend, llm_model=llm_model,
        save_prompts=save_prompts,
    )
