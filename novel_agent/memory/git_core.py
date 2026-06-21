"""Git 核心——严格遵循 git 模型。

数据模型：
  - 工作区 = memory/ + state.json + scenes/（始终反映 HEAD）
  - commit = 不可变的项目快照（parent 指针形成 DAG）
  - tree = commit 对应的工作区完整快照
  - branch = refs/heads/<name>（指向 commit hash）
  - tag = refs/tags/<name>（存档，固定引用）
  - HEAD = 指向当前分支
  - reflog = 记录每次 ref 变更
  - .inkforge/objects/ = 对象数据库（所有 commit + tree，永不删除）
"""

import hashlib
import json
import logging
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GitRepo:
    """一个项目目录下的最小 Git 仓库。"""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.git_dir = self.project_dir / ".inkforge"
        self.objects_dir = self.git_dir / "objects"
        self.refs_heads = self.git_dir / "refs" / "heads"
        self.refs_tags = self.git_dir / "refs" / "tags"
        self.head_file = self.git_dir / "HEAD"
        self.logs_dir = self.git_dir / "logs"

    # ── 初始化 ──────────────────────────────────────────

    def init(self) -> None:
        for d in [self.objects_dir, self.refs_heads, self.refs_tags,
                  self.logs_dir / "refs" / "heads"]:
            d.mkdir(parents=True, exist_ok=True)
        if not self.head_file.exists():
            self.head_file.write_text("ref: refs/heads/main", encoding="utf-8")

    # ── hash / object helpers ───────────────────────────

    @staticmethod
    def _sha1(data: str) -> str:
        return hashlib.sha1(data.encode("utf-8")).hexdigest()

    def _object_path(self, h: str) -> Path:
        return self.objects_dir / h[:2] / h[2:]

    def _write_object(self, h: str, content: str) -> None:
        p = self._object_path(h)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def _read_object(self, h: str) -> str:
        return self._object_path(h).read_text(encoding="utf-8")

    # ── ref helpers ─────────────────────────────────────

    def _read_ref(self, ref_path: Path) -> Optional[str]:
        if not ref_path.exists():
            return None
        return ref_path.read_text(encoding="utf-8").strip()

    def _write_ref(self, ref_path: Path, h: str) -> None:
        ref_path.parent.mkdir(parents=True, exist_ok=True)
        ref_path.write_text(h + "\n", encoding="utf-8")

    def _delete_ref(self, ref_path: Path) -> None:
        if ref_path.exists():
            ref_path.unlink()

    # ── HEAD ────────────────────────────────────────────

    def resolve_head(self) -> Optional[str]:
        head = self._read_ref(self.head_file)
        if not head:
            return None
        if head.startswith("ref: "):
            ref_path = self.git_dir / head[5:]
            return self._read_ref(ref_path)
        return head

    def head_branch(self) -> str:
        head = self._read_ref(self.head_file)
        if head and head.startswith("ref: refs/heads/"):
            return head[16:]
        return "main"

    # ── tree 快照（完整工作区） ─────────────────────────

    def _snapshot_working_tree(self) -> str:
        """序列化整个工作区 → JSON 字符串。包含 memory/（不含 ChromaDB index）+ state.json + scenes/。"""
        data = {"_type": "tree"}
        for subdir in ["memory", "scenes"]:
            d = self.project_dir / subdir
            if d.exists():
                data[subdir] = _serialize_directory(d, skip_patterns=["index/", ".sqlite3", ".bin", "chroma.sqlite3"])
            else:
                data[subdir] = {}
        sf = self.project_dir / "state.json"
        if sf.exists():
            data["state_json"] = sf.read_text(encoding="utf-8")
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    def _restore_working_tree(self, json_data: str) -> None:
        """从 JSON 恢复工作区。兼容新旧两种 tree 格式。

        index/ 目录永不触碰——ChromaDB 持有 SQLite 连接，move 会改变 inode
        导致 SQLITE_READONLY_DBMOVED。index 不在 tree 中，无需恢复。
        """
        data = json.loads(json_data)

        if data.get("_type") == "tree":
            mem_data = data.get("memory", "{}")
            scenes_data = data.get("scenes")
            state_raw = data.get("state_json")
        else:
            mem_data = json_data
            scenes_data = None
            state_raw = None

        # 恢复 memory/ — 只删非 index 的子目录/文件，不动 index/
        mem_dir = self.project_dir / "memory"
        index_dir = mem_dir / "index"
        if mem_dir.exists():
            for child in list(mem_dir.iterdir()):
                if child.name == "index":
                    continue  # 永不触碰 ChromaDB 索引
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
        if mem_data:
            _restore_directory(mem_dir, mem_data if isinstance(mem_data, str) else json.dumps(mem_data, ensure_ascii=False))
        else:
            mem_dir.mkdir(parents=True, exist_ok=True)
        # 确保 index 目录存在（首次 checkout 时可能还没有）
        index_dir.mkdir(parents=True, exist_ok=True)

        # 恢复 scenes/（仅新格式有此字段）
        if scenes_data:
            scenes_dir = self.project_dir / "scenes"
            if scenes_dir.exists():
                shutil.rmtree(scenes_dir)
            _restore_directory(scenes_dir, scenes_data if isinstance(scenes_data, str) else json.dumps(scenes_data, ensure_ascii=False))

        # 恢复 state.json（仅新格式有此字段）
        if state_raw:
            (self.project_dir / "state.json").write_text(state_raw, encoding="utf-8")

        # 恢复后 ChromaDB 索引可能和实体不同步——标记待刷新
        # 不删除不重建，只记录。下次访问时 VectorStore 检测并自动修复。

    # ── commit ──────────────────────────────────────────

    def commit(self, tick: int, message: str = "", scene_file: str = "") -> str:
        """创建提交：保存工作区快照，更新 ref。"""
        self.init()

        # 1. 更新 state.json tick
        sf = self.project_dir / "state.json"
        if sf.exists():
            state = json.loads(sf.read_text(encoding="utf-8"))
            state["current_tick"] = tick
            state["current_branch"] = self.head_branch()
            sf.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        # 2. tree 快照
        tree_data = self._snapshot_working_tree()
        tree_hash = self._sha1(tree_data)
        self._write_object(tree_hash, tree_data)

        # 3. parent
        parent = self.resolve_head()

        # 4. commit 对象
        ts = datetime.now(timezone.utc).isoformat()
        raw = f"{tick}|{parent or ''}|{tree_hash}|{message}|{scene_file}|{ts}"
        commit_hash = self._sha1(raw)
        self._write_object(commit_hash, json.dumps({
            "hash": commit_hash, "parent": parent, "tick": tick,
            "tree_hash": tree_hash, "message": message,
            "scene_file": scene_file, "timestamp": ts,
        }, ensure_ascii=False, indent=2))

        # 5. 更新分支 ref
        branch = self.head_branch()
        old_hash = self._read_ref(self.refs_heads / branch)
        self._write_ref(self.refs_heads / branch, commit_hash)

        # 6. reflog
        self._log_ref("HEAD", old_hash, commit_hash, f"commit: {message}")
        self._log_ref(f"refs/heads/{branch}", old_hash, commit_hash, f"commit: {message}")

        logger.debug("commit: %s tick=%d parent=%s", commit_hash[:8], tick, (parent or "none")[:8])
        return commit_hash

    # ── log ─────────────────────────────────────────────

    def log(self, max_count: int = 20) -> list[dict]:
        current = self.resolve_head()
        commits = []
        seen = set()
        while current and len(commits) < max_count:
            if current in seen:
                break
            seen.add(current)
            try:
                obj = json.loads(self._read_object(current))
                commits.append(obj)
                current = obj.get("parent")
            except (FileNotFoundError, json.JSONDecodeError):
                break
        return commits

    def get_commit(self, h: str) -> Optional[dict]:
        try:
            return json.loads(self._read_object(h))
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    # ── branch ──────────────────────────────────────────

    def create_branch(self, name: str, target_hash: str = "") -> str:
        if not target_hash:
            target_hash = self.resolve_head() or ""
        if not target_hash:
            raise ValueError("没有可用的 commit")
        ref_path = self.refs_heads / name
        if ref_path.exists():
            raise ValueError(f"分支已存在: {name}")
        self._write_ref(ref_path, target_hash)
        self._log_ref(f"refs/heads/{name}", "", target_hash, f"branch: Created from HEAD")
        logger.info("branch: %s → %s", name, target_hash[:8])
        return name

    def list_branches(self) -> list[dict]:
        current = self.head_branch()
        result = []
        for ref_file in sorted(self.refs_heads.glob("*")):
            if ref_file.is_file():
                name = ref_file.name
                h = self._read_ref(ref_file)
                c = self.get_commit(h) if h else None
                result.append({
                    "name": name, "hash": h,
                    "tick": c["tick"] if c else 0,
                    "message": c["message"] if c else "",
                    "active": name == current,
                })
        result.sort(key=lambda b: (0 if b["name"] == "main" else 1, b["name"]))
        return result

    def delete_branch(self, name: str) -> None:
        if name == "main":
            raise ValueError("不能删除 main 分支")
        self._delete_ref(self.refs_heads / name)

    # ── checkout ────────────────────────────────────────

    def checkout(self, target: str) -> dict:
        """切换分支/commit —— 恢复完整工作区。"""
        ref_path = self.refs_heads / target
        if ref_path.exists():
            commit_hash = self._read_ref(ref_path)
            branch_name = target
        else:
            commit_hash = target
            branch_name = ""

        if not commit_hash:
            raise ValueError(f"无效目标: {target}")
        commit = self.get_commit(commit_hash)
        if not commit:
            raise ValueError(f"commit 不存在: {commit_hash}")

        # 恢复完整工作区
        tree_hash = commit.get("tree_hash", "")
        if tree_hash:
            tree_data = self._read_object(tree_hash)
            self._restore_working_tree(tree_data)

        # 确保 state.json tick 正确（tree 可能已包含正确值，这里兜底）
        sf = self.project_dir / "state.json"
        if sf.exists():
            state = json.loads(sf.read_text(encoding="utf-8"))
            state["current_tick"] = commit["tick"]
            state["current_branch"] = branch_name or self.head_branch()
            state.pop("branch_heads", None); state.pop("fork_points", None)
            state.pop("fork_backups", None); state.pop("branches", None)
            state.pop("scene_branches", None)
            sf.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        # 更新 HEAD
        if branch_name:
            self.head_file.write_text(f"ref: refs/heads/{branch_name}", encoding="utf-8")
        else:
            self.head_file.write_text(commit_hash, encoding="utf-8")

        self._log_ref("HEAD", "", commit_hash, f"checkout: {target}")
        logger.info("checkout: %s → tick=%d", target, commit["tick"])
        return {"branch": branch_name, "hash": commit_hash, "tick": commit["tick"]}

    # ── reset ───────────────────────────────────────────

    def reset(self, target_hash: str, mode: str = "mixed") -> dict:
        """回滚到指定 commit。

        soft:  只移动 ref（不改工作区）
        mixed: 移动 ref + 恢复工作区（默认）
        hard:  同 mixed（工作区已完全恢复）
        """
        target = self.get_commit(target_hash)
        if not target:
            raise ValueError(f"commit 不存在: {target_hash}")

        branch = self.head_branch()
        old_hash = self._read_ref(self.refs_heads / branch)

        if mode in ("mixed", "hard"):
            tree_hash = target.get("tree_hash", "")
            if tree_hash:
                tree_data = self._read_object(tree_hash)
                self._restore_working_tree(tree_data)
            # 兜底更新 state.json
            sf = self.project_dir / "state.json"
            if sf.exists():
                state = json.loads(sf.read_text(encoding="utf-8"))
                state["current_tick"] = target["tick"]
                state["current_branch"] = branch
                state.pop("branch_heads", None); state.pop("fork_points", None)
                state.pop("fork_backups", None); state.pop("branches", None)
                state.pop("scene_branches", None)
                sf.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        self._write_ref(self.refs_heads / branch, target_hash)
        self._log_ref(f"refs/heads/{branch}", old_hash, target_hash,
                      f"reset --{mode}: to {target_hash[:8]}")
        logger.info("reset --%s: %s → %s (tick %d)", mode, (old_hash or "?")[:8],
                     target_hash[:8], target["tick"])
        return {"hash": target_hash, "tick": target["tick"], "branch": branch}

    def fork_before_reset(self, target_hash: str) -> Optional[str]:
        branch = self.head_branch()
        old_hash = self._read_ref(self.refs_heads / branch)
        if not old_hash or old_hash == target_hash:
            return None
        old = self.get_commit(old_hash)
        tgt = self.get_commit(target_hash)
        if not old or not tgt or old["tick"] <= tgt["tick"]:
            return None
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        fork_name = f"fork_{ts}"
        self.create_branch(fork_name, old_hash)
        return fork_name

    # ── tag ─────────────────────────────────────────────

    def create_tag(self, name: str, message: str = "") -> str:
        head_hash = self.resolve_head()
        if not head_hash:
            raise ValueError("没有可用的 commit")
        self._write_ref(self.refs_tags / name, head_hash)
        self._log_ref(f"refs/tags/{name}", "", head_hash, f"tag: {message}")
        logger.info("tag: %s → %s", name, head_hash[:8])
        return name

    def list_tags(self) -> list[dict]:
        result = []
        for tag_file in sorted(self.refs_tags.glob("*")):
            if tag_file.is_file():
                name = tag_file.name
                h = self._read_ref(tag_file)
                c = self.get_commit(h) if h else None
                result.append({
                    "name": name, "hash": h,
                    "tick": c["tick"] if c else 0,
                    "message": c["message"] if c else "",
                    "timestamp": c["timestamp"] if c else "",
                })
        return result

    def delete_tag(self, name: str) -> None:
        self._delete_ref(self.refs_tags / name)

    # ── reflog ──────────────────────────────────────────

    def _log_ref(self, ref_name: str, old_hash: str, new_hash: str, action: str) -> None:
        log_file = self.logs_dir / f"{ref_name}.log" if "/" not in ref_name else self.logs_dir / f"{ref_name.replace('/', '_')}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).isoformat()
        zero = "0000000000000000000000000000000000000000"
        line = f"{old_hash or zero} {new_hash} {ts}\t{action}\n"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line)

    def reflog(self, ref_name: str = "HEAD", max_count: int = 20) -> list[dict]:
        log_file = self.logs_dir / f"{ref_name}.log" if "/" not in ref_name else self.logs_dir / f"{ref_name.replace('/', '_')}.log"
        if not log_file.exists():
            return []
        entries = []
        with open(log_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(" ", 3)
                if len(parts) >= 3:
                    entries.append({
                        "old_hash": parts[0] if parts[0] != "0000000000000000000000000000000000000000" else "",
                        "new_hash": parts[1], "timestamp": parts[2],
                        "action": parts[3].lstrip("\t") if len(parts) > 3 else "",
                    })
        return list(reversed(entries[-max_count:]))

    # ── 迁移 ────────────────────────────────────────────

    def needs_migration(self) -> bool:
        return (self.project_dir / "state.json").exists() and not self.head_file.exists()

    def migrate_from_legacy(self) -> None:
        """从旧系统迁移到 git 模型。当前状态成为唯一 commit。"""
        self.init()
        sf = self.project_dir / "state.json"
        if not sf.exists():
            return
        state = json.loads(sf.read_text(encoding="utf-8"))
        tick = state.get("current_tick", 0)

        # 保存当前完整快照
        tree_data = self._snapshot_working_tree()
        tree_hash = self._sha1(tree_data)
        self._write_object(tree_hash, tree_data)

        # 创建迁移 commit
        raw = f"{tick}||{tree_hash}|migration||migrated"
        commit_hash = self._sha1(raw)
        self._write_object(commit_hash, json.dumps({
            "hash": commit_hash, "parent": None, "tick": tick,
            "tree_hash": tree_hash, "message": "migration",
            "scene_file": "", "timestamp": "migrated",
        }, ensure_ascii=False, indent=2))

        self._write_ref(self.refs_heads / "main", commit_hash)
        self.head_file.write_text("ref: refs/heads/main", encoding="utf-8")

        # 迁移旧存档为 tags
        cp_dir = self.project_dir / "checkpoints"
        if cp_dir.exists():
            for d in cp_dir.iterdir():
                if d.is_dir() and (d / "manifest.json").exists():
                    try:
                        mf = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
                        self._write_ref(self.refs_tags / d.name, commit_hash)
                    except Exception:
                        pass

        logger.info("迁移完成: tick=%d", tick)


# ═══════════════════════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════════════════════

def _serialize_directory(dir_path: Path, skip_patterns: list[str] | None = None) -> str:
    """将整个目录序列化为 JSON。跳过二进制文件和指定模式。"""
    if not dir_path.exists():
        return "{}"
    skip = skip_patterns or []
    BINARY_EXTS = {".db", ".sqlite", ".sqlite3", ".bin", ".pickle", ".pkl", ".parquet"}
    data = {}
    for root, dirs, files in os.walk(dir_path):
        # 跳过 index/ 等二进制目录
        dirs[:] = [d for d in dirs if not any(p in f"{os.path.relpath(root, dir_path)}/{d}/" for p in skip)]
        rel = os.path.relpath(root, dir_path)
        if rel == ".":
            rel = ""
        for fname in sorted(files):
            fpath = Path(root) / fname
            key = f"{rel}/{fname}" if rel else fname
            # 跳过二进制扩展名
            if any(fname.endswith(ext) for ext in BINARY_EXTS):
                continue
            # 跳过匹配 skip_patterns 的文件
            if any(p in key for p in skip):
                continue
            try:
                data[key] = fpath.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue  # 静默跳过二进制文件
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _restore_directory(dir_path: Path, json_data: str) -> None:
    """从 JSON 恢复整个目录。"""
    data = json.loads(json_data) if isinstance(json_data, str) else json_data
    if dir_path.exists():
        shutil.rmtree(dir_path)
    dir_path.mkdir(parents=True, exist_ok=True)
    for fname, content in data.items():
        if content == "[binary]":
            continue
        fpath = dir_path / fname
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content, encoding="utf-8")
