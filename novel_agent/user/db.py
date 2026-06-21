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
    expires_at TEXT,
    strict_expiry INTEGER NOT NULL DEFAULT 1
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

CREATE TABLE IF NOT EXISTS community_posts (
    project_id   TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    published    INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS community_comments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   TEXT NOT NULL,
    user_id      TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    chapter_tick INTEGER,
    paragraph    INTEGER,
    content      TEXT NOT NULL,
    parent_id    INTEGER DEFAULT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS community_chat (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   TEXT DEFAULT NULL,
    user_id      TEXT NOT NULL,
    display_name TEXT NOT NULL,
    message      TEXT NOT NULL,
    created_at   TEXT NOT NULL
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
            # 启动自愈：修复上次异常关闭导致的 WAL 锁死
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.executescript(_SCHEMA)
            # Migrations for existing databases
            for col in ("activate_ip", "last_ip"):
                try:
                    conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
                except sqlite3.OperationalError:
                    pass
            for col in ("password_hash", "salt"):
                try:
                    conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
                except sqlite3.OperationalError:
                    pass
            try:
                conn.execute("ALTER TABLE users ADD COLUMN disabled INTEGER NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE invite_codes ADD COLUMN strict_expiry INTEGER NOT NULL DEFAULT 1")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE community_chat ADD COLUMN project_id TEXT DEFAULT NULL")
            except sqlite3.OperationalError:
                pass
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

    def register_user(self, invite_code: str, display_name: str, password_hash: str, salt: str, ip: str = "") -> str:
        """Create a new user with password. Returns user_id."""
        now = datetime.utcnow().isoformat()
        user_id = secrets.token_hex(6)
        code = invite_code.strip().upper()
        with self._connect() as conn:
            row = conn.execute("SELECT is_admin FROM invite_codes WHERE code = ?", (code,)).fetchone()
            is_admin = row["is_admin"] if row else 0
            conn.execute(
                "INSERT INTO users (user_id, invite_code, display_name, created_at, last_seen, "
                "is_admin, activate_ip, last_ip, password_hash, salt, disabled) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (user_id, code, display_name.strip(), now, now, is_admin, ip, ip, password_hash, salt)
            )
            conn.commit()
        return user_id

    def get_user_by_name(self, display_name: str) -> Optional[dict]:
        """Find user by display name (for login)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id, invite_code, display_name, is_admin, password_hash, salt, "
                "disabled, created_at, last_seen FROM users WHERE display_name = ?",
                (display_name.strip(),)
            ).fetchone()
        return dict(row) if row else None

    def set_password(self, user_id: str, password_hash: str, salt: str):
        """Reset password for a user."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, salt = ? WHERE user_id = ?",
                (password_hash, salt, user_id)
            )
            conn.commit()

    def update_display_name(self, user_id: str, display_name: str):
        with self._connect() as conn:
            conn.execute("UPDATE users SET display_name = ? WHERE user_id = ?",
                         (display_name.strip(), user_id))
            conn.commit()

    def set_user_disabled(self, user_id: str, disabled: bool):
        with self._connect() as conn:
            conn.execute("UPDATE users SET disabled = ? WHERE user_id = ?",
                         (1 if disabled else 0, user_id))
            conn.commit()

    def list_all_users(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT u.user_id, u.display_name, u.is_admin, u.disabled, u.created_at, u.last_seen, "
                "COUNT(p.id) as project_count "
                "FROM users u LEFT JOIN projects p ON u.user_id = p.user_id "
                "GROUP BY u.user_id ORDER BY u.created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def list_codes(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT c.*, u.display_name as used_by FROM invite_codes c "
                "LEFT JOIN users u ON c.code = u.invite_code "
                "ORDER BY c.created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def is_code_expired_for_user(self, user_id: str) -> bool:
        """检查用户的邀请码是否已过期且 strict_expiry=1。返回 True 表示应拦截登录。"""
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT c.expires_at, c.strict_expiry FROM invite_codes c "
                "JOIN users u ON u.invite_code = c.code "
                "WHERE u.user_id = ?", (user_id,)
            ).fetchone()
        if not row or not row["expires_at"]:
            return False
        if not row["strict_expiry"]:
            return False  # 管理员关闭了严格过期
        return now > row["expires_at"]

    def get_code_expiry(self, code: str) -> Optional[str]:
        """获取邀请码的过期时间。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT expires_at FROM invite_codes WHERE code = ?",
                (code.strip().upper(),)
            ).fetchone()
        return row["expires_at"] if row else None

    def toggle_strict_expiry(self, code: str) -> bool:
        """切换 strict_expiry。返回新值。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT strict_expiry FROM invite_codes WHERE code = ?",
                (code.strip().upper(),)
            ).fetchone()
            if not row:
                return False
            new_val = 0 if row["strict_expiry"] else 1
            conn.execute(
                "UPDATE invite_codes SET strict_expiry = ? WHERE code = ?",
                (new_val, code.strip().upper())
            )
            conn.commit()
            return bool(new_val)

    def update_code_expiry(self, code: str, days: int):
        """更新邀请码过期时间。days=0 表示永不过期。"""
        expires = (datetime.utcnow() + timedelta(days=days)).isoformat() if days > 0 else None
        with self._connect() as conn:
            conn.execute(
                "UPDATE invite_codes SET expires_at = ? WHERE code = ?",
                (expires, code.strip().upper())
            )
            conn.commit()

    def revoke_code(self, code: str):
        with self._connect() as conn:
            conn.execute("DELETE FROM invite_codes WHERE code = ?", (code.strip().upper(),))
            conn.commit()

    def get_stats(self) -> dict:
        with self._connect() as conn:
            users = conn.execute("SELECT COUNT(*) as n FROM users").fetchone()["n"]
            active = conn.execute("SELECT COUNT(*) as n FROM users WHERE disabled=0").fetchone()["n"]
            projects = conn.execute("SELECT COUNT(*) as n FROM projects").fetchone()["n"]
            codes = conn.execute(
                "SELECT COUNT(*) as n FROM invite_codes WHERE used < max_uses "
                "AND (expires_at IS NULL OR expires_at > ?)",
                (datetime.utcnow().isoformat(),)
            ).fetchone()["n"]
        return {"total_users": users, "active_users": active, "total_projects": projects, "available_codes": codes}

    def count_online_users(self, minutes: int = 5) -> int:
        """统计最近 N 分钟内有请求的用户数。middleware 每次请求更新 last_seen。"""
        with self._connect() as conn:
            cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
            row = conn.execute(
                "SELECT COUNT(DISTINCT user_id) as n FROM users WHERE last_seen >= ? AND disabled = 0",
                (cutoff,)
            ).fetchone()
        return row["n"] if row else 0

    def get_daily_activity(self, days: int = 30) -> list[dict]:
        """最近 N 天每天的活跃用户数和项目数。"""
        with self._connect() as conn:
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            rows = conn.execute("""
                SELECT DATE(last_seen) as day,
                       COUNT(DISTINCT user_id) as users,
                       COUNT(DISTINCT (SELECT COUNT(*) FROM projects p2
                           WHERE p2.user_id = u.user_id AND p2.last_accessed >= ?)) as active_projects
                FROM users u
                WHERE last_seen >= ?
                GROUP BY day ORDER BY day
            """, (cutoff, cutoff)).fetchall()
            return [{"day": r["day"], "users": r["users"], "active_projects": r["active_projects"]} for r in rows]

    def get_top_users(self, limit: int = 10) -> list[dict]:
        """最活跃用户排行（按项目数+最近活跃）。"""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT u.display_name, u.last_seen,
                       COUNT(p.project_id) as project_count
                FROM users u LEFT JOIN projects p ON u.user_id = p.user_id
                WHERE u.disabled = 0
                GROUP BY u.user_id ORDER BY u.last_seen DESC, project_count DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [{"display_name": r["display_name"], "last_seen": r["last_seen"], "project_count": r["project_count"]} for r in rows]

    # ── community ─────────────────────────────────────────────────────────

    def set_publish(self, project_id: str, user_id: str, published: bool) -> bool:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute("PRAGMA foreign_keys=OFF")
            if published:
                conn.execute(
                    "INSERT OR REPLACE INTO community_posts (project_id, user_id, published, created_at) VALUES (?, ?, 1, ?)",
                    (project_id, user_id, now)
                )
            else:
                conn.execute("DELETE FROM community_posts WHERE project_id = ?", (project_id,))
            conn.execute("PRAGMA foreign_keys=ON")
            conn.commit()
        return published

    def get_publish_status(self, project_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT published FROM community_posts WHERE project_id = ?", (project_id,)
            ).fetchone()
        return bool(row and row["published"])

    def list_published_posts(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT p.project_id, p.user_id, p.created_at, COALESCE(u.display_name, p.user_id) as display_name "
                "FROM community_posts p LEFT JOIN users u ON p.user_id = u.user_id "
                "WHERE p.published = 1 ORDER BY p.created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def add_comment(self, project_id: str, user_id: str, display_name: str,
                    content: str, chapter_tick: int = None, paragraph: int = None,
                    parent_id: int = None) -> dict:
        now = datetime.utcnow().isoformat()
        name = display_name or user_id
        with self._connect() as conn:
            conn.execute("PRAGMA foreign_keys=OFF")
            cur = conn.execute(
                "INSERT INTO community_comments (project_id, user_id, display_name, chapter_tick, paragraph, content, parent_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, user_id, name, chapter_tick, paragraph, content, parent_id, now)
            )
            conn.commit()
            return {"id": cur.lastrowid, "created_at": now}

    def get_comments(self, project_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM community_comments WHERE project_id = ? ORDER BY created_at ASC",
                (project_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def update_comment(self, comment_id: int, user_id: str, content: str) -> bool:
        """编辑评论（仅本人）。"""
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE community_comments SET content = ? WHERE id = ? AND user_id = ?",
                (content, comment_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def delete_comment(self, comment_id: int, user_id: str) -> bool:
        """删除评论（仅本人）。"""
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM community_comments WHERE id = ? AND user_id = ?",
                (comment_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def add_chat_message(self, user_id: str, display_name: str, message: str, project_id: str = None) -> dict:
        now = datetime.utcnow().isoformat()
        name = display_name or user_id
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO community_chat (project_id, user_id, display_name, message, created_at) VALUES (?, ?, ?, ?, ?)",
                (project_id, user_id, name, message, now)
            )
            # 限制每个频道最多保留 500 条，超出删旧
            conn.execute(
                "DELETE FROM community_chat WHERE project_id IS ? AND id NOT IN ("
                "SELECT id FROM community_chat WHERE project_id IS ? ORDER BY id DESC LIMIT 500"
                ")", (project_id, project_id)
            )
            conn.commit()
            return {"id": cur.lastrowid, "created_at": now}

    def get_chat_messages(self, project_id: str = None, since_id: int = 0, limit: int = 200) -> list[dict]:
        pid_filter = "project_id IS NULL" if project_id is None else "project_id = ?"
        params: list = [project_id] if project_id is not None else []
        with self._connect() as conn:
            if since_id > 0:
                rows = conn.execute(
                    f"SELECT * FROM community_chat WHERE {pid_filter} AND id > ? ORDER BY id ASC LIMIT ?",
                    params + [since_id, limit]
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT * FROM community_chat WHERE {pid_filter} ORDER BY id DESC LIMIT ?",
                    params + [limit]
                ).fetchall()
        result = [dict(r) for r in rows]
        return list(reversed(result)) if since_id == 0 else result

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
