"""Git 风格分支管理器——独立模块，不侵入核心逻辑。

模型（直接映射 git 概念）：
  - scene = commit（有 parent tick）
  - branch = 具名指针，存的是 head tick
  - HEAD = current_tick + current_branch
  - fork = 回滚到旧节点后，原路线保留为分叉分支
  - 存档 = tag（固定引用）

所有状态存储在 state.json 的三个字段中：
  branch_heads: {"main": 12, "fork_001": 15}   — 每个分支指向的 head tick
  fork_points: {"fork_001": 8}                   — 分叉发生在哪个 tick
  current_branch: "main"                          — 当前活跃分支
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _read_state(state_path: Path) -> dict:
    if state_path.exists():
        return json.loads(state_path.read_text(encoding="utf-8"))
    return {}


def _write_state(state_path: Path, state: dict) -> None:
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ═══════════════════════════════════════════════════════
# 分支操作
# ═══════════════════════════════════════════════════════

def fork_on_restore(project_dir: Path, old_tick: int, backup_checkpoint_id: str = "") -> Optional[str]:
    """回滚到更早 tick 时调用——旧路线保存为分叉分支。

    Args:
        project_dir: 项目目录
        old_tick: 回滚前的 current_tick
        backup_checkpoint_id: 备份存档 ID（前端切换用）

    Returns:
        新分叉分支名，无分叉则返回 None
    """
    state_path = project_dir / "state.json"
    state = _read_state(state_path)
    restored_tick = state.get("current_tick", 0)

    if old_tick <= restored_tick:
        return None  # 回滚到同一 tick 或未来，不分叉

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    fork_name = f"fork_{ts}"

    state.setdefault("branch_heads", {})
    state.setdefault("fork_points", {})

    # main 指针移到回滚点
    state["branch_heads"]["main"] = restored_tick
    # 旧位置存为分叉
    state["branch_heads"][fork_name] = old_tick
    state["fork_points"][fork_name] = restored_tick
    state["current_branch"] = "main"

    if backup_checkpoint_id:
        state.setdefault("fork_backups", {})[fork_name] = backup_checkpoint_id

    # 清理旧字段
    state.pop("branches", None)
    state.pop("scene_branches", None)

    _write_state(state_path, state)
    logger.info("分叉分支已创建: %s (tick %d → %d)", fork_name, restored_tick, old_tick)
    return fork_name


def advance_branch(project_dir: Path) -> None:
    """生成新场景后调用——当前分支指针前移 1。

    由 scene_committer.commit_scene 调用，不侵入核心逻辑。
    """
    state_path = project_dir / "state.json"
    state = _read_state(state_path)
    tick = state.get("current_tick", 0)
    branch = state.get("current_branch", "main")

    state.setdefault("branch_heads", {})
    state["branch_heads"][branch] = tick

    _write_state(state_path, state)


def switch_branch(project_dir: Path, branch_name: str) -> dict:
    """切换到指定分支——移动 HEAD 到该分支的 head tick。

    Args:
        project_dir: 项目目录
        branch_name: 目标分支名（"main" 或 "fork_xxx"）

    Returns:
        {"switched": True, "branch": branch_name, "current_tick": N}
    """
    state_path = project_dir / "state.json"
    state = _read_state(state_path)
    heads = state.get("branch_heads", {})

    if branch_name not in heads:
        raise ValueError(f"分支不存在: {branch_name}（可用: {list(heads.keys())}）")

    state["current_branch"] = branch_name
    state["current_tick"] = heads[branch_name]
    _write_state(state_path, state)
    logger.info("切换到分支 %s (tick %d)", branch_name, heads[branch_name])
    return {"switched": True, "branch": branch_name, "current_tick": heads[branch_name]}


def list_branches(state: dict) -> list:
    """列出所有分支及其信息（给前端）。"""
    heads = state.get("branch_heads", {})
    forks = state.get("fork_points", {})
    backups = state.get("fork_backups", {})
    result = []
    for name, head_tick in heads.items():
        result.append({
            "name": name,
            "head_tick": head_tick,
            "forked_from": forks.get(name),
            "backup_checkpoint_id": backups.get(name, ""),
            "active": state.get("current_branch") == name,
        })
    return result


# ═══════════════════════════════════════════════════════
# 时间线树构建
# ═══════════════════════════════════════════════════════

def build_timeline(project_dir: Path) -> dict:
    """构建完整时间线树——主干 + 分支 + 存档节点。

    纯数据层：只读，不修改任何文件。
    """
    import re

    state_path = project_dir / "state.json"
    state = _read_state(state_path)
    scenes_dir = project_dir / "scenes"

    current_tick = state.get("current_tick", 0)
    current_branch = state.get("current_branch", "main")
    heads = state.get("branch_heads", {"main": current_tick})
    forks = state.get("fork_points", {})
    backups = state.get("fork_backups", {})

    nodes = []

    # 扫描所有场景文件
    if scenes_dir.exists():
        for f in sorted(scenes_dir.iterdir()):
            m = re.match(r"scene_(\d+)\.md(?:\.(\d{8}_\d{6})\.bak)?", f.name)
            if not m:
                continue
            tick = int(m.group(1))
            branch = "main"
            archived = False

            if m.group(2):  # .bak 文件
                archived = True
                branch = f"fork_{m.group(2)}"
            else:
                # 判断该 tick 属于哪个非活跃分支
                # 规则：tick 超出某非活跃分支的 fork 点但不超过其 head → 属于该分支
                for fname, fhead in heads.items():
                    if fname == current_branch:
                        continue
                    ffork = forks.get(fname, 0)
                    if ffork < tick <= fhead:
                        branch = fname
                        archived = True
                        break
                # 如果没匹配到任何非活跃分支，保持 main（共享历史或 active branch）

            # 读标题
            title = ""
            try:
                first = f.read_text(encoding="utf-8").split("\n")[0]
                first = re.sub(r"^#\s*第\d+章\s*", "", first).strip()
                title = first[:40]
            except Exception:
                pass

            nodes.append({
                "tick": tick,
                "branch": branch,
                "title": title,
                "file": f.name,
                "archived": archived,
                "active": branch == current_branch,
            })

    # 补充分支中没有对应 .md 文件的虚拟节点
    for fname, fhead in heads.items():
        if fname == "main":
            continue
        ffork = forks.get(fname, 0)
        for t in range(ffork + 1, fhead + 1):
            if not any(n["tick"] == t and n["branch"] == fname for n in nodes):
                nodes.append({
                    "tick": t,
                    "branch": fname,
                    "title": "",
                    "file": f"scene_{t:03d}.md",
                    "archived": True,
                    "active": fname == current_branch,
                })

    # 活跃分支包含所有从 0 到 head 的 tick（共享历史 + 独有）
    active_head = heads.get(current_branch, current_tick)
    active_ticks = {n["tick"] for n in nodes if n["branch"] == current_branch}
    for n in list(nodes):
        if n["tick"] <= active_head and n["tick"] not in active_ticks:
            nodes.append({
                "tick": n["tick"],
                "branch": current_branch,
                "title": n["title"],
                "file": n["file"],
                "archived": False,
                "active": True,
            })
            active_ticks.add(n["tick"])

    nodes.sort(key=lambda n: (n["tick"], n["branch"]))

    branches = list_branches(state)

    return {
        "current_tick": current_tick,
        "current_branch": current_branch,
        "nodes": nodes,
        "branches": branches,
    }
