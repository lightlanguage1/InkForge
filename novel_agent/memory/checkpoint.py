"""存档系统——基于 git tag + reset。"""

import json
import logging
from pathlib import Path
from typing import List
from datetime import datetime
from dataclasses import dataclass, asdict

from .git_core import GitRepo

logger = logging.getLogger(__name__)


@dataclass
class CheckpointManifest:
    checkpoint_id: str
    tick: int
    timestamp: str
    scenes_count: int = 0
    characters_count: int = 0
    locations_count: int = 0
    size_bytes: int = 0
    created_by: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CheckpointManifest":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def get_checkpoint_dir(project_dir: Path) -> Path:
    return project_dir / "checkpoints"


def get_checkpoint_id(tick: int) -> str:
    return f"checkpoint_tick_{tick:03d}"


def create_checkpoint(project_dir: Path, tick: int, created_by: str = "manual") -> str:
    """创建存档——git tag。"""
    repo = GitRepo(project_dir)
    repo.init()
    if repo.needs_migration():
        repo.migrate_from_legacy()

    # 旧 checkpoints 目录保留用于向后兼容的 manifest 索引
    checkpoints_dir = get_checkpoint_dir(project_dir)
    checkpoints_dir.mkdir(exist_ok=True)

    base_id = get_checkpoint_id(tick)
    if created_by == "auto":
        tag_name = base_id
        existing = repo.list_tags()
        if any(t["name"] == tag_name for t in existing):
            logger.info("自动存档已存在，跳过: %s", tag_name)
            return tag_name
    else:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        tag_name = f"{base_id}_{ts}"

    # 统计信息
    memory_dir = project_dir / "memory"
    scenes_count = len(list((project_dir / "scenes").glob("scene_*.md"))) if (project_dir / "scenes").exists() else 0
    chars_count = len(list((memory_dir / "characters").glob("*.json"))) if (memory_dir / "characters").exists() else 0
    locs_count = len(list((memory_dir / "locations").glob("*.json"))) if (memory_dir / "locations").exists() else 0

    repo.create_tag(tag_name, created_by)

    # 保存 manifest 到旧 checkpoints 目录（兼容）
    manifest = CheckpointManifest(
        checkpoint_id=tag_name, tick=tick,
        timestamp=datetime.now().isoformat(),
        scenes_count=scenes_count, characters_count=chars_count,
        locations_count=locs_count, created_by=created_by,
    )
    manifest_path = checkpoints_dir / f"{tag_name}_manifest.json"
    manifest_path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("存档已创建: %s (tick %d)", tag_name, tick)
    return tag_name


def list_checkpoints(project_dir: Path) -> List[CheckpointManifest]:
    """列出所有存档。"""
    checkpoints_dir = get_checkpoint_dir(project_dir)
    if not checkpoints_dir.exists():
        return []
    manifests = []
    for mf in checkpoints_dir.glob("*_manifest.json"):
        try:
            manifests.append(CheckpointManifest.from_dict(json.loads(mf.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return sorted(manifests, key=lambda m: m.tick)


def restore_checkpoint(project_dir: Path, checkpoint_id: str) -> dict:
    """恢复存档——git reset --mixed。

    旧路线自动分叉保存。
    """
    repo = GitRepo(project_dir)
    repo.init()

    # 查找 tag
    tags = repo.list_tags()
    tag_info = None
    for t in tags:
        if t["name"] == checkpoint_id:
            tag_info = t
            break
    if not tag_info:
        # 兼容旧的 checkpoint 目录
        raise ValueError(f"存档不存在: {checkpoint_id}")

    # 分叉
    repo.fork_before_reset(tag_info["hash"])

    # reset --mixed（恢复 memory，保留 scenes）
    result = repo.reset(tag_info["hash"], mode="mixed")

    return {"restored": checkpoint_id, "tick": result["tick"], "branch": result["branch"]}


def delete_checkpoint(project_dir: Path, checkpoint_id: str) -> None:
    """删除存档。"""
    repo = GitRepo(project_dir)
    repo.delete_tag(checkpoint_id)
    # 也清理旧 manifest
    mf = get_checkpoint_dir(project_dir) / f"{checkpoint_id}_manifest.json"
    if mf.exists():
        mf.unlink()


def should_create_checkpoint(current_tick: int, checkpoint_interval: int,
                             last_checkpoint_tick=None) -> bool:
    if checkpoint_interval <= 0:
        return False
    if last_checkpoint_tick is None:
        return current_tick > 0 and current_tick % checkpoint_interval == 0
    return current_tick - last_checkpoint_tick >= checkpoint_interval
