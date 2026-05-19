"""Checkpoint command - manage project checkpoints."""
import json
from pathlib import Path
from typing import Optional
from ...memory.checkpoint import (
    create_checkpoint,
    list_checkpoints,
    restore_checkpoint,
    delete_checkpoint
)


def create_checkpoint_cmd(project_dir: Path, message: Optional[str] = None):
    """Create a checkpoint command wrapper.
    
    Args:
        project_dir: Path to project directory
        message: Optional description message
    """
    # Load current tick
    state_file = project_dir / "state.json"
    if not state_file.exists():
        print("[ERR] 未找到 state.json")
        return
    
    with open(state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)
        current_tick = state.get('current_tick', 0)
    
    created_by = message if message else "manual"
    
    try:
        checkpoint_path = create_checkpoint(project_dir, current_tick, created_by)
        print(f"[OK] 存档已创建：{checkpoint_path.name}")
        print(f"   幕数：{current_tick}")
        if message:
            print(f"   备注：{message}")
    except IOError as e:
        print(f"[ERR] 创建存档失败：{e}")


def list_checkpoints_cmd(project_dir: Path):
    """List checkpoints command wrapper.
    
    Args:
        project_dir: Path to project directory
    """
    manifests = list_checkpoints(project_dir)
    
    if not manifests:
        print("\n 暂无存档\n")
        return
    
    print(f"\n 存档列表（共 {len(manifests)} 个）\n")
    
    for manifest in manifests:
        print(f"  {manifest.checkpoint_id}")
        print(f"    幕数：{manifest.tick}")
        print(f"    创建时间：{manifest.timestamp}")
        print(f"    场景数：{manifest.scenes_count}")
        print(f"    角色数：{manifest.characters_count}")
        print(f"    地点数：{manifest.locations_count}")
        size_mb = manifest.size_bytes / (1024 * 1024)
        print(f"    大小：{size_mb:.2f} MB")
        print(f"    创建者：{manifest.created_by}")
        print()


def restore_checkpoint_cmd(project_dir: Path, checkpoint_id: str):
    """Restore checkpoint command wrapper.
    
    Args:
        project_dir: Path to project directory
        checkpoint_id: Checkpoint ID to restore
    """
    print(f"[WARN]  即将恢复项目状态至：{checkpoint_id}")
    print("   当前状态将自动备份。")
    
    # Confirm
    response = input("\nContinue? [y/N]: ")
    if response.lower() != 'y':
        print("已取消。")
        return

    try:
        restore_checkpoint(project_dir, checkpoint_id, backup_current=True)
        print(f"[OK] 存档已恢复：{checkpoint_id}")
        print("   当前状态已备份至 checkpoints/backup_before_restore_*")
    except (ValueError, IOError) as e:
        print(f"[ERR] 恢复存档失败：{e}")


def delete_checkpoint_cmd(project_dir: Path, checkpoint_id: str):
    """Delete checkpoint command wrapper.
    
    Args:
        project_dir: Path to project directory
        checkpoint_id: Checkpoint ID to delete
    """
    print(f"[WARN]  即将永久删除：{checkpoint_id}")
    
    # Confirm
    response = input("\nContinue? [y/N]: ")
    if response.lower() != 'y':
        print("已取消。")
        return

    try:
        delete_checkpoint(project_dir, checkpoint_id)
        print(f"[OK] 存档已删除：{checkpoint_id}")
    except (ValueError, IOError) as e:
        print(f"[ERR] 删除存档失败：{e}")
