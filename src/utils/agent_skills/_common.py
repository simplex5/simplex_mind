"""
Tool: Shared constants and helpers for all agent-skill tools
Purpose: Single source of truth for repo paths, sqlite row conversion, ticket
         priority ordering, the standard CLI epilogue, and optional dotenv
         loading — previously duplicated across ~15 scripts (SIMP-L1-033).

Import pattern from a subpackage (memory/, tickets/, ...):
    try:
        from .._common import REPO_ROOT, row_to_dict
    except ImportError:
        import sys; from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from _common import REPO_ROOT, row_to_dict

From a same-directory tool (project_resolver, git_commit, init):
    try:
        from ._common import REPO_ROOT
    except ImportError:
        from _common import REPO_ROOT
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# _common.py lives at src/utils/agent_skills/ — three parents up is the repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
DATABASE_DIR = REPO_ROOT / "database"
MEMORY_DIR = DATABASE_DIR / "memory"

# Ticket priority ordering — keep the map and the SQL CASE in lockstep.
PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
PRIORITY_SQL_CASE = (
    "CASE priority "
    + " ".join(f"WHEN '{name}' THEN {rank}" for name, rank in PRIORITY_ORDER.items())
    + " END"
)


# ── Timestamp convention (SIMP-L1-034) ──────────────────────────────────────
# All stored timestamps are UTC. Two formats exist, one per database family,
# and they must not be mixed WITHIN a database (string comparisons rely on it):
#   - tickets.db / memory.db columns default to SQLite CURRENT_TIMESTAMP
#     ('YYYY-MM-DD HH:MM:SS') → write with utc_now_db()
#   - conversation_history.db stores ISO-8601 Z ('YYYY-MM-DDTHH:MM:SSZ')
#     → write with utc_now_iso_z()
DB_TS_FMT = "%Y-%m-%d %H:%M:%S"
ISO_Z_FMT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now_db() -> str:
    """UTC now in SQLite CURRENT_TIMESTAMP format (tickets.db, memory.db)."""
    return datetime.now(timezone.utc).strftime(DB_TS_FMT)


def utc_now_iso_z() -> str:
    """UTC now in ISO-8601 Z format (conversation_history.db, index metadata)."""
    return datetime.now(timezone.utc).strftime(ISO_Z_FMT)


def row_to_dict(row) -> Optional[Dict]:
    """Convert sqlite3.Row (or None) to a plain dict."""
    if row is None:
        return None
    return dict(row)


def cli_finish(result: Dict[str, Any], ok: str = "") -> None:
    """Standard CLI epilogue: ERROR + exit(1) on failure; OK line + JSON on success."""
    if not result.get("success"):
        print(f"ERROR {result.get('error', 'Unknown error')}")
        sys.exit(1)
    print(f"OK {ok or result.get('message', '')}".rstrip())
    print(json.dumps(result, indent=2, default=str))


def load_dotenv_if_available() -> None:
    """Load .env from the repo root when python-dotenv is installed; no-op otherwise."""
    try:
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass
