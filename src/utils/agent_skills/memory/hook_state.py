"""
Tool: Hook State Store (database/hooks.db)
Purpose: Durable per-session state + append-only event log for the hook layer
         (SIMP-D2-038). Replaces the per-session temp-JSON files that
         protocol_gate and subconscious_recall kept in the system temp dir —
         those leaked forever (never cleaned), died on temp wipes, and left no
         queryable trail of what the enforcement layer actually did.

Two tables:
    hook_session_state — one JSON blob per (session, hook): the once-per-session
        throttle state the hooks already kept, now durable and inspectable.
    hook_events — append-only observability: one row per check outcome plus one
        'invocation' row per hook run (with duration_ms). This is the
        measurement substrate the reports batch called for: gate fire rates
        decide warn->deny, invocation latency decides the warm-daemon question,
        piece injection counts decide whether subconscious pieces earn their
        keep. Rows older than RETENTION_DAYS are pruned opportunistically on
        write, so the log stays bounded (no new unbounded-growth store).

Contract: every public function is fail-open and silent — hook state must
never crash a hook or block a prompt. A broken hooks.db degrades to
"fresh session every prompt" (once-per-session throttles re-fire: noisy,
never blocking). doctor.py reads this DB for health reporting.
"""

import json
import sqlite3
import sys
from pathlib import Path

try:
    from .._common import REPO_ROOT as _REPO_ROOT
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from _common import REPO_ROOT as _REPO_ROOT

DB_PATH = _REPO_ROOT / "database" / "hooks.db"
RETENTION_DAYS = 90

_SCHEMA = """
CREATE TABLE IF NOT EXISTS hook_session_state (
    session_id TEXT NOT NULL,
    hook TEXT NOT NULL,
    state TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (session_id, hook)
);
CREATE TABLE IF NOT EXISTS hook_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    hook TEXT NOT NULL,
    check_name TEXT,
    outcome TEXT NOT NULL,
    reason TEXT,
    duration_ms INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_hook_events_created ON hook_events(created_at);
CREATE INDEX IF NOT EXISTS idx_hook_events_hook ON hook_events(hook, outcome);
"""


def get_connection() -> sqlite3.Connection:
    """WAL from day one — multiple hooks write here on every prompt."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn


def get_state(hook: str, session_id: str, default=None):
    """Load the JSON state blob for (session, hook). Fail-open: `default`."""
    try:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT state FROM hook_session_state WHERE session_id = ? AND hook = ?",
                (session_id, hook)).fetchone()
        finally:
            conn.close()
        if row:
            return json.loads(row["state"])
    except Exception:
        pass
    return default


def set_state(hook: str, session_id: str, state) -> bool:
    """Upsert the JSON state blob. Fail-open: returns False, never raises."""
    try:
        conn = get_connection()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO hook_session_state (session_id, hook, state) VALUES (?, ?, ?)",
                (session_id, hook, json.dumps(state)))
            conn.commit()
        finally:
            conn.close()
        return True
    except Exception:
        return False


def log_event(hook: str, session_id: str = None, check_name: str = None,
              outcome: str = "fired", reason: str = "",
              duration_ms: int = None) -> bool:
    """Append one observability row; prunes rows past retention on the way.
    Fail-open: returns False, never raises."""
    try:
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO hook_events (session_id, hook, check_name, outcome, reason, duration_ms) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, hook, check_name, outcome, reason or None, duration_ms))
            conn.execute(
                "DELETE FROM hook_events WHERE created_at < datetime('now', ?)",
                (f"-{RETENTION_DAYS} days",))
            conn.commit()
        finally:
            conn.close()
        return True
    except Exception:
        return False
