"""公告数据库 — 独立 SQLite 表，不影响核心引擎。"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any


_SCHEMA = """
CREATE TABLE IF NOT EXISTS announcements (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    content    TEXT NOT NULL DEFAULT '',
    tag        TEXT NOT NULL DEFAULT '公告',
    active     INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
"""


class AnnouncementDB:
    """公告的轻量 SQLite 操作。"""

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
            conn.executescript(_SCHEMA)

    # ── 公开 ──

    def list_active(self, limit: int = 5) -> List[Dict[str, Any]]:
        """获取当前有效的公告，最新在前。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM announcements WHERE active = 1 ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── 管理 ──

    def create(self, title: str, content: str, tag: str = "公告") -> int:
        """创建公告，返回 ID。"""
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO announcements (title, content, tag, active, created_at)
                   VALUES (?, ?, ?, 1, ?)""",
                (title, content, tag, datetime.now(timezone.utc).isoformat()),
            )
            return cur.lastrowid

    def update(self, ann_id: int, title: str = "", content: str = "", tag: str = "", active: int | None = None) -> bool:
        """更新公告字段。"""
        with self._connect() as conn:
            sets = []
            vals = []
            if title:
                sets.append("title = ?"); vals.append(title)
            if content:
                sets.append("content = ?"); vals.append(content)
            if tag:
                sets.append("tag = ?"); vals.append(tag)
            if active is not None:
                sets.append("active = ?"); vals.append(active)
            if not sets:
                return False
            vals.append(ann_id)
            conn.execute(f"UPDATE announcements SET {', '.join(sets)} WHERE id = ?", vals)
            return True

    def delete(self, ann_id: int) -> bool:
        """软删除（设 inactive）。"""
        with self._connect() as conn:
            conn.execute("UPDATE announcements SET active = 0 WHERE id = ?", (ann_id,))
            return True

    def list_all(self) -> List[Dict[str, Any]]:
        """管理端：列出所有公告（含已归档）。"""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM announcements ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]
