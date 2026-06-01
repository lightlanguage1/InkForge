"""InkForge beta monitoring — runs every 30 minutes, appends to monitor.log."""
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://inkforge.irynekoneko.club/api/v1"
TOKEN = ""  # will be refreshed each run
LOG_PATH = Path(__file__).parent / "monitor.log"


def api(method, path, body=None):
    """Make an API call with auth."""
    global TOKEN
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def refresh_token():
    """Get fresh auth token."""
    global TOKEN
    code, data = api("POST", "/auth/activate",
                     {"invite_code": "IF-0E617B72", "display_name": "monitor"})
    TOKEN = data.get("token", "")


def check_health():
    """Health endpoint."""
    t0 = time.time()
    try:
        req = urllib.request.Request("https://inkforge.irynekoneko.club/health", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            elapsed = time.time() - t0
            return resp.status == 200, elapsed
    except Exception:
        return False, time.time() - t0


def check_projects():
    """List all projects."""
    status, data = api("GET", "/projects")
    if status == 200:
        projects = data.get("projects", [])
        return len(projects), projects
    return 0, []


def check_project_status(project_id):
    """Get detailed status for a project."""
    status, data = api("GET", f"/project/{project_id}/status")
    if status == 200:
        return data
    return {}


def check_users():
    """Check DB for user count."""
    try:
        import sqlite3
        conn = sqlite3.connect("/app/work/inkforge.db")
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        codes_total = conn.execute("SELECT COUNT(*) FROM invite_codes").fetchone()[0]
        codes_used = conn.execute("SELECT COUNT(*) FROM invite_codes WHERE used > 0").fetchone()[0]
        conn.close()
        return users, codes_total, codes_used
    except Exception:
        return 0, 0, 0


def log(msg):
    """Append timestamped entry to monitor log."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"[{ts}] {msg}")


def main():
    log("=== InkForge Beta Monitor ===")

    # 1. Health
    ok, elapsed = check_health()
    log(f"Health: {'OK' if ok else 'FAIL'} ({elapsed:.2f}s)")

    # 2. Auth
    try:
        refresh_token()
        log("Auth: OK")
    except Exception as e:
        log(f"Auth: FAIL - {e}")
        return

    # 3. Projects overview
    count, projects = check_projects()
    log(f"Projects: {count} total")

    # 4. Per-project stats
    total_ticks = 0
    total_scenes = 0
    total_words = 0
    generating = 0
    for p in projects:
        pid = p.get("project_id", "?")
        name = p.get("novel_name", "?")
        detail = check_project_status(pid)
        tick = detail.get("current_tick", 0)
        scenes = detail.get("scene_count", 0)
        words = detail.get("word_count", 0)
        gen = detail.get("generating", False)
        total_ticks += tick
        total_scenes += scenes
        total_words += words
        if gen:
            generating += 1
        log(f"  [{pid}] {name}: tick={tick} scenes={scenes} words={words} gen={gen}")

    # 5. Summary
    log(f"Summary: ticks={total_ticks} scenes={total_scenes} words={total_words} generating={generating}")

    # 6. Users
    users, codes_total, codes_used = check_users()
    log(f"Users: {users}  Codes: {codes_used}/{codes_total} used")


if __name__ == "__main__":
    main()
