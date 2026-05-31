"""SQLite database — users, invite codes, projects. Single-file, zero-dependency."""
import sqlite3
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS invite_codes (
    code       TEXT PRIMARY KEY,
    max_uses   INTEGER NOT NULL DEFAULT 1,
    used       INTEGER NOT NULL DEFAULT 0,
    is_admin   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS users (
    user_id      TEXT PRIMARY KEY,
    invite_code  TEXT NOT NULL,
    display_name TEXT NOT NULL,
    is_admin     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    last_seen    TEXT NOT NULL,
    FOREIGN KEY (invite_code) REFERENCES invite_codes(code)
);

CREATE TABLE IF NOT EXISTS projects (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       TEXT NOT NULL,
    project_id    TEXT NOT NULL,
    project_name  TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    last_accessed TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    UNIQUE(user_id, project_id)
);
"""


class Database:
    """Thin wrapper around sqlite3 for InkForge user management."""

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
            # Migration: add IP tracking columns for existing databases
            for col in ("activate_ip", "last_ip"):
                try:
                    conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
                except sqlite3.OperationalError:
                    pass  # column already exists
            conn.commit()

    # ── invite codes ──────────────────────────────────────────────────────

    def validate_code(self, code: str) -> Optional[str]:
        """Check an invite code is valid and not exhausted. Returns error msg or None."""
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT max_uses, used, expires_at FROM invite_codes WHERE code = ?",
                (code.strip().upper(),)
            ).fetchone()

        if not row:
            return "邀请码无效"
        if row["expires_at"] and now > row["expires_at"]:
            return "邀请码已过期"
        if row["used"] >= row["max_uses"]:
            return "邀请码已达使用上限"
        return None

    def consume_code(self, code: str) -> bool:
        """Increment usage count. Returns False if already full."""
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE invite_codes SET used = used + 1 "
                "WHERE code = ? AND used < max_uses",
                (code.strip().upper(),)
            )
            conn.commit()
            return cur.rowcount > 0

    def generate_codes(self, count: int = 10, max_uses: int = 1, days: int = 30) -> list[str]:
        """Generate invite codes. Returns the code strings."""
        codes = []
        now = datetime.utcnow().isoformat()
        expires = (datetime.utcnow() + timedelta(days=days)).isoformat() if days > 0 else None
        with self._connect() as conn:
            for _ in range(count):
                code = "IF-" + secrets.token_hex(4).upper()[:8]
                conn.execute(
                    "INSERT INTO invite_codes (code, max_uses, used, created_at, expires_at) "
                    "VALUES (?, ?, 0, ?, ?)",
                    (code, max_uses, now, expires)
                )
                codes.append(code)
            conn.commit()
        return codes

    # ── users ────────────────────────────────────────────────────────────

    def get_or_create_user(self, invite_code: str, display_name: str, ip: str = "") -> str:
        """Create a user from a valid invite code. Returns user_id."""
        now = datetime.utcnow().isoformat()
        user_id = secrets.token_hex(6)
        code = invite_code.strip().upper()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT is_admin FROM invite_codes WHERE code = ?", (code,)
            ).fetchone()
            is_admin = row["is_admin"] if row else 0
            conn.execute(
                "INSERT INTO users (user_id, invite_code, display_name, created_at, last_seen, is_admin, activate_ip, last_ip) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, code, display_name.strip(), now, now, is_admin, ip, ip)
            )
            conn.commit()
        return user_id

    def touch_user(self, user_id: str, ip: str = ""):
        """Update last_seen and last_ip (for audit, not enforcement)."""
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            if ip:
                conn.execute(
                    "UPDATE users SET last_seen = ?, last_ip = ? WHERE user_id = ?",
                    (now, ip, user_id)
                )
            else:
                conn.execute(
                    "UPDATE users SET last_seen = ? WHERE user_id = ?",
                    (now, user_id)
                )
            conn.commit()

    def get_user(self, user_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id, invite_code, display_name, is_admin, created_at, last_seen "
                "FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_user_by_invite_code(self, code: str) -> Optional[dict]:
        """Find existing user by invite code (for re-login)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id, invite_code, display_name, is_admin, created_at, last_seen "
                "FROM users WHERE invite_code = ?", (code.strip().upper(),)
            ).fetchone()
        return dict(row) if row else None

    # ── projects ─────────────────────────────────────────────────────────

    def list_projects(self, user_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT project_id, project_name, created_at, last_accessed "
                "FROM projects WHERE user_id = ? ORDER BY last_accessed DESC",
                (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def upsert_project(self, user_id: str, project_id: str, project_name: str):
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO projects (user_id, project_id, project_name, created_at, last_accessed) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id, project_id) DO UPDATE SET "
                "  last_accessed = excluded.last_accessed, "
                "  project_name  = excluded.project_name",
                (user_id, project_id, project_name, now, now)
            )
            conn.commit()
