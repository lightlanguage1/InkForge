"""Git 风格分支管理器——包装 GitRepo，对上层提供简洁 API。

模型（直接映射 git 概念）：
  - scene = commit（有 parent 指针）
  - branch = refs/heads/<name>（指向 commit hash）
  - HEAD = current_branch
  - fork = reset 前自动创建分支保存旧路线
  - 存档 = tag（固定引用）
"""

import json
import logging
from pathlib import Path
from typing import Optional

from .git_core import GitRepo

logger = logging.getLogger(__name__)


def _get_repo(project_dir: Path) -> GitRepo:
    repo = GitRepo(project_dir)
    # 自动迁移
    if repo.needs_migration():
        logger.info("检测到旧版本数据，正在迁移到 git 模型...")
        repo.migrate_from_legacy()
    else:
        repo.init()
    return repo


# ═══════════════════════════════════════════════════════
# 分支操作
# ═══════════════════════════════════════════════════════

def fork_on_restore(project_dir: Path, old_tick: int, backup_id: str = "") -> Optional[str]:
    """回滚到更早 tick 时调用——旧路线保存为分叉分支。"""
    repo = _get_repo(project_dir)
    head = repo.resolve_head()
    if not head:
        return None
    current = repo.get_commit(head)
    if not current or current["tick"] <= old_tick:
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fork_name = f"fork_{ts}"
    repo.create_branch(fork_name, head)
    return fork_name


def advance_branch(project_dir: Path) -> None:
    """生成新场景后调用——当前分支指针已由 commit 更新，无需额外操作。"""
    pass  # commit 已经更新了 ref


def switch_branch(project_dir: Path, branch_name: str) -> dict:
    """切换到指定分支——git checkout <branch>

    Returns:
        {"switched": True, "branch": name, "current_tick": N}
    """
    repo = _get_repo(project_dir)
    result = repo.checkout(branch_name)
    return {"switched": True, "branch": result["branch"], "current_tick": result["tick"]}


def list_branches(project_dir: Path) -> list:
    """列出所有分支及其信息（给前端）。"""
    repo = _get_repo(project_dir)
    return repo.list_branches()


def delete_branch(project_dir: Path, name: str) -> None:
    repo = _get_repo(project_dir)
    repo.delete_branch(name)


# ═══════════════════════════════════════════════════════
# 时间线树构建
# ═══════════════════════════════════════════════════════

def build_timeline(project_dir: Path) -> dict:
    """构建完整时间线树——基于 git commit 链。

    纯数据层：只读，不修改任何文件。
    """
    import re
    from datetime import datetime as _dt

    repo = _get_repo(project_dir)
    state_file = project_dir / "state.json"
    state = {}
    if state_file.exists():
        state = json.loads(state_file.read_text(encoding="utf-8"))

    current_tick = state.get("current_tick", 0)
    current_branch = repo.head_branch()

    # 收集所有 commit
    all_commits = {}
    for obj_dir in sorted(repo.objects_dir.glob("[0-9a-f][0-9a-f]")):
        for obj_file in sorted(obj_dir.glob("*")):
            try:
                c = json.loads(obj_file.read_text(encoding="utf-8"))
                if "hash" in c and "tick" in c:
                    all_commits[c["hash"]] = c
            except (json.JSONDecodeError, OSError):
                continue

    # 构建分支→commit 的映射
    branch_heads = {}
    for b in repo.list_branches():
        branch_heads[b["name"]] = b["hash"]

    # 收集所有 commit hash，按 tick 分组
    tick_commits: dict[int, list[dict]] = {}
    for c in all_commits.values():
        tick_commits.setdefault(c["tick"], []).append(c)

    # 构建节点
    nodes = []
    for tick_val in sorted(tick_commits):
        commits = tick_commits[tick_val]
        # 确定这个 tick 属于哪个分支
        for c in commits:
            branch = "main"
            archived = False
            active = c["hash"] == repo.resolve_head()

            # 检查是否属于非活跃分支
            for bname, bhash in branch_heads.items():
                if bhash == c["hash"] and bname != current_branch:
                    branch = bname
                    archived = True
                    break

            # 读标题
            title = c.get("message", "")
            scene_file = c.get("scene_file", f"scene_{tick_val:03d}.md")

            nodes.append({
                "tick": tick_val,
                "hash": c["hash"],
                "parent": c.get("parent", ""),
                "branch": branch if archived else current_branch,
                "title": title,
                "file": scene_file,
                "archived": archived,
                "active": branch == current_branch or c["hash"] == repo.resolve_head(),
            })

    # 去重：同一 tick 可能有多个节点（分叉），保留当前分支的和最新的
    seen = {}
    for n in sorted(nodes, key=lambda x: (x["tick"], 0 if x["branch"] == current_branch else 1)):
        key = (n["tick"], n["branch"])
        seen[key] = n
    nodes = sorted(seen.values(), key=lambda n: (n["tick"], n["branch"]))

    # tags（存档点）
    checkpoints = []
    for tag in repo.list_tags():
        checkpoints.append({
            "id": tag["name"],
            "tick": tag["tick"],
            "hash": tag["hash"],
            "label": tag.get("message", "") or tag["name"],
        })

    return {
        "current_tick": current_tick,
        "current_branch": current_branch,
        "current_hash": repo.resolve_head() or "",
        "nodes": nodes,
        "branches": repo.list_branches(),
        "checkpoints": checkpoints,
    }
