"""音乐收藏数据库 — 独立的 SQLite 表，不混入核心引擎。"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any


_SCHEMA = """
CREATE TABLE IF NOT EXISTS music_favorites (
    user_id    TEXT NOT NULL,
    song_id    TEXT NOT NULL,
    title      TEXT NOT NULL,
    artist     TEXT NOT NULL,
    album      TEXT NOT NULL DEFAULT '',
    duration   INTEGER NOT NULL DEFAULT 0,
    artwork    TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, song_id)
);
"""


class MusicDB:
    """音乐收藏的轻量 SQLite 操作。"""

    def __init__(self, db_path: str = "work/inkforge.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init(self):
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    # ── CRUD ──

    def add_favorite(self, user_id: str, song: Dict[str, Any]) -> bool:
        """收藏一首歌，已存在则忽略。返回是否新插入。"""
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT 1 FROM music_favorites WHERE user_id = ? AND song_id = ?",
                (user_id, song["id"]),
            )
            if cur.fetchone():
                return False
            conn.execute(
                """INSERT INTO music_favorites (user_id, song_id, title, artist, album, duration, artwork, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    song["id"],
                    song["title"],
                    song["artist"],
                    song.get("album", ""),
                    song.get("duration", 0),
                    song.get("artwork", ""),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            return True

    def remove_favorite(self, user_id: str, song_id: str) -> bool:
        """取消收藏。返回是否删除了记录。"""
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM music_favorites WHERE user_id = ? AND song_id = ?",
                (user_id, song_id),
            )
            return cur.rowcount > 0

    def get_favorites(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的所有收藏，按时间倒序。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM music_favorites WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            return [
                {
                    "id": r["song_id"],
                    "mid": r["song_id"],
                    "title": r["title"],
                    "artist": r["artist"],
                    "album": r["album"],
                    "duration": r["duration"],
                    "artwork": r["artwork"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

    def is_favorite(self, user_id: str, song_id: str) -> bool:
        """检查是否已收藏。"""
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT 1 FROM music_favorites WHERE user_id = ? AND song_id = ?",
                (user_id, song_id),
            )
            return cur.fetchone() is not None

    def get_favorite_ids(self, user_id: str) -> set:
        """获取用户收藏的所有 song_id（用于前端高亮）。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT song_id FROM music_favorites WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            return {r["song_id"] for r in rows}
