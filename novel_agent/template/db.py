"""文风 & 写作方法模板数据库 — 两张独立的表。"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any


_STYLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS style_templates (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    description    TEXT NOT NULL DEFAULT '',
    prompt_snippet TEXT NOT NULL DEFAULT '',
    is_preset      INTEGER NOT NULL DEFAULT 0,
    user_id        TEXT DEFAULT NULL,
    created_at     TEXT NOT NULL
);
"""

_CRAFT_SCHEMA = """
CREATE TABLE IF NOT EXISTS craft_templates (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    description    TEXT NOT NULL DEFAULT '',
    prompt_snippet TEXT NOT NULL DEFAULT '',
    is_preset      INTEGER NOT NULL DEFAULT 0,
    user_id        TEXT DEFAULT NULL,
    created_at     TEXT NOT NULL
);
"""


class TemplateDB:
    """文风/写作方法的轻量 SQLite 操作，两张表复用同一套 CRUD。"""

    def __init__(self, db_path: str = "work/inkforge.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init(self):
        with self._connect() as conn:
            conn.executescript(_STYLE_SCHEMA)
            conn.executescript(_CRAFT_SCHEMA)

    def _table(self, template_type: str) -> str:
        if template_type == "craft":
            return "craft_templates"
        return "style_templates"

    # ── 公开 ──

    def get_presets(self, template_type: str) -> List[Dict[str, Any]]:
        """获取某类型的所有预设。"""
        table = self._table(template_type)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE is_preset = 1 ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_public(self, template_type: str) -> List[Dict[str, Any]]:
        """获取某类型的公开共享模板（非预设、无 user_id）。"""
        table = self._table(template_type)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE is_preset = 0 AND user_id IS NULL ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_by_id(self, template_type: str, template_id: str) -> Optional[Dict[str, Any]]:
        """按 ID 获取模板。"""
        table = self._table(template_type)
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT * FROM {table} WHERE id = ?", (template_id,)
            ).fetchone()
        return dict(row) if row else None

    # ── 用户管理 ──

    def list_user(self, template_type: str, user_id: str) -> List[Dict[str, Any]]:
        """获取某用户在某类型下的所有模板。"""
        table = self._table(template_type)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def insert_if_not_exists(self, template_id: str, name: str, description: str,
                              prompt_snippet: str, template_type: str, is_preset: bool = False,
                              user_id: str = None) -> bool:
        """插入模板（已存在则跳过），用于安装预设。"""
        table = self._table(template_type)
        with self._connect() as conn:
            cur = conn.execute(f"SELECT 1 FROM {table} WHERE id = ?", (template_id,))
            if cur.fetchone():
                return False
            conn.execute(
                f"INSERT INTO {table} (id, name, description, prompt_snippet, is_preset, user_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (template_id, name, description, prompt_snippet, int(is_preset), user_id,
                 datetime.now(timezone.utc).isoformat()),
            )
            return True

    def create(self, name: str, description: str, prompt_snippet: str,
               template_type: str, user_id: str) -> str:
        """创建用户自定义模板，返回生成的 ID。"""
        import uuid
        template_id = f"{template_type}_{uuid.uuid4().hex[:8]}"
        table = self._table(template_type)
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO {table} (id, name, description, prompt_snippet, is_preset, user_id, created_at) "
                "VALUES (?, ?, ?, ?, 0, ?, ?)",
                (template_id, name, description, prompt_snippet, user_id,
                 datetime.now(timezone.utc).isoformat()),
            )
        return template_id

    def update(self, template_type: str, template_id: str, user_id: str,
               name: str = "", description: str = "", prompt_snippet: str = "") -> bool:
        """更新模板（仅本人）。"""
        table = self._table(template_type)
        with self._connect() as conn:
            sets = []; vals = []
            if name: sets.append("name = ?"); vals.append(name)
            if description: sets.append("description = ?"); vals.append(description)
            if prompt_snippet: sets.append("prompt_snippet = ?"); vals.append(prompt_snippet)
            if not sets: return False
            vals.extend([template_id, user_id])
            cur = conn.execute(
                f"UPDATE {table} SET {', '.join(sets)} WHERE id = ? AND user_id = ?", vals
            )
            return cur.rowcount > 0

    def delete(self, template_type: str, template_id: str, user_id: str) -> bool:
        """删除模板（仅本人，预设不可删）。"""
        table = self._table(template_type)
        with self._connect() as conn:
            cur = conn.execute(
                f"DELETE FROM {table} WHERE id = ? AND user_id = ? AND is_preset = 0",
                (template_id, user_id),
            )
            return cur.rowcount > 0
