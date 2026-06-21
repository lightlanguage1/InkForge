"""一次性迁移脚本——将旧格式 .inkforge tree 升级为新格式。

旧格式: tree 对象顶层是 memory/ 序列化后的 JSON
新格式: {"_type":"tree","memory":"...","scenes":"...","state_json":"..."}

用法:
  cd /app && python novel_agent/migrate_trees.py /app/work/users/<user_id>/novels/<project_id>

迁移完后删除本文件即可。
"""

import hashlib
import json
import os
import sys
from pathlib import Path


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def serialize_dir(d: Path) -> str:
    if not d.exists():
        return "{}"
    data = {}
    for root, dirs, files in os.walk(d):
        rel = os.path.relpath(root, d)
        if rel == ".":
            rel = ""
        for fname in sorted(files):
            key = f"{rel}/{fname}" if rel else fname
            try:
                data[key] = (Path(root) / fname).read_text(encoding="utf-8")
            except Exception:
                data[key] = "[binary]"
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def object_path(objects_dir: Path, h: str) -> Path:
    return objects_dir / h[:2] / h[2:]


def migrate(project_dir: Path):
    git_dir = project_dir / ".inkforge"
    objects_dir = git_dir / "objects"
    if not objects_dir.exists():
        print("未找到 .inkforge/objects/，无需迁移")
        return

    scenes_dir = project_dir / "scenes"
    state_file = project_dir / "state.json"
    scenes_snapshot = serialize_dir(scenes_dir)
    state_snapshot = state_file.read_text(encoding="utf-8") if state_file.exists() else "{}"

    # ── 第一步：升级所有旧格式 tree ──
    old_to_new_tree: dict[str, str] = {}
    upgraded = 0

    for h2_dir in sorted(objects_dir.glob("[0-9a-f][0-9a-f]")):
        for obj_file in sorted(h2_dir.glob("*")):
            full_hash = h2_dir.name + obj_file.name
            content = obj_file.read_text(encoding="utf-8")
            try:
                data = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                continue

            # 判断: 新格式有 _type="tree"
            if isinstance(data, dict) and data.get("_type") == "tree":
                continue  # 已是新格式

            # 旧格式: 整个 data 就是 memory/ 的序列化
            new_tree = {
                "_type": "tree",
                "memory": content,  # 旧数据原样放进 memory 字段
                "scenes": scenes_snapshot,
                "state_json": state_snapshot,
            }
            new_content = json.dumps(new_tree, ensure_ascii=False, separators=(",", ":"))
            new_hash = sha1(new_content)

            new_path = object_path(objects_dir, new_hash)
            if new_path.exists():
                print(f"  跳过 (hash 冲突): {full_hash[:12]}")
                continue

            new_path.parent.mkdir(parents=True, exist_ok=True)
            new_path.write_text(new_content, encoding="utf-8")
            old_to_new_tree[full_hash] = new_hash
            upgraded += 1
            print(f"  tree: {full_hash[:12]} → {new_hash[:12]}")

    print(f"升级了 {upgraded} 个 tree")

    # ── 第二步：更新引用旧 tree 的 commit ──
    if not old_to_new_tree:
        # 也升级 commit 对象中的 tree_hash 引用
        pass

    old_to_new_commit: dict[str, str] = {}
    recommitted = 0

    for h2_dir in sorted(objects_dir.glob("[0-9a-f][0-9a-f]")):
        for obj_file in sorted(h2_dir.glob("*")):
            full_hash = h2_dir.name + obj_file.name
            content = obj_file.read_text(encoding="utf-8")
            try:
                data = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                continue

            # 判断是否是 commit
            if not isinstance(data, dict) or "tree_hash" not in data:
                continue

            old_tree = data.get("tree_hash", "")
            if old_tree not in old_to_new_tree:
                continue

            # 更新 commit 的 tree_hash
            data["tree_hash"] = old_to_new_tree[old_tree]
            new_content = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            new_hash = sha1(new_content)

            new_path = object_path(objects_dir, new_hash)
            if not new_path.exists():
                new_path.parent.mkdir(parents=True, exist_ok=True)
                new_path.write_text(new_content, encoding="utf-8")

            old_to_new_commit[full_hash] = new_hash
            recommitted += 1
            print(f"  commit: {full_hash[:12]} → {new_hash[:12]}")

    print(f"更新了 {recommitted} 个 commit")

    # ── 第三步：更新 refs ──
    for ref_type in ["heads", "tags"]:
        ref_dir = git_dir / "refs" / ref_type
        if not ref_dir.exists():
            continue
        for ref_file in ref_dir.glob("*"):
            if not ref_file.is_file():
                continue
            old_ref = ref_file.read_text(encoding="utf-8").strip()
            if old_ref in old_to_new_commit:
                new_ref = old_to_new_commit[old_ref]
                ref_file.write_text(new_ref + "\n", encoding="utf-8")
                print(f"  ref {ref_type}/{ref_file.name}: {old_ref[:12]} → {new_ref[:12]}")

    # ── 第四步：更新 HEAD ──
    head_file = git_dir / "HEAD"
    if head_file.exists():
        head = head_file.read_text(encoding="utf-8").strip()
        if head.startswith("ref: "):
            pass  # 符号引用，已在上面更新
        elif head in old_to_new_commit:
            head_file.write_text(old_to_new_commit[head] + "\n", encoding="utf-8")
            print(f"  HEAD: {head[:12]} → {old_to_new_commit[head][:12]}")

    print("迁移完成")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python migrate_trees.py <project_dir>")
        print("示例: python migrate_trees.py /app/work/users/xxx/novels/my_project_abc")
        sys.exit(1)

    migrate(Path(sys.argv[1]))
