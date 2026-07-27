"""
Tool: Backup — copy every brain database to a timestamped local directory
Purpose: `simplex backup` (SIMP-D2-027). Uses SQLite's online backup API, so
         copies are consistent even while the DBs are in use by hooks/cron.

Usage:
    python src/utils/agent_skills/backup_db.py             # -> database/backups/<UTC>/
    python src/utils/agent_skills/backup_db.py --dest D:/somewhere

Covers: memory.db, the brain tickets.db, every registered project's
tickets.db (skipped with a note when a project has none yet), and
conversation_history.db. The default destination lives under database/,
which is gitignored — backups never reach git. No scheduling; run it
manually or wire it into your own cron/Task Scheduler if wanted.
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys_path_entry = str(Path(__file__).parent)
if sys_path_entry not in sys.path:
    sys.path.insert(0, sys_path_entry)

try:
    from ._common import REPO_ROOT
except ImportError:
    from _common import REPO_ROOT

try:
    from . import project_resolver
except ImportError:
    import project_resolver


def _sources() -> list:
    """(label, source path) for every DB worth backing up."""
    sources = [
        ("memory.db", REPO_ROOT / "database" / "memory" / "memory.db"),
        ("conversation_history.db", REPO_ROOT / "database" / "conversation_history.db"),
        ("tickets/simplex_mind.db", REPO_ROOT / "database" / "tickets.db"),
    ]
    for proj in project_resolver.get_all_projects():
        if proj["name"] == "simplex_mind":
            continue
        sources.append((f"tickets/{proj['name']}.db",
                        Path(proj["path"]) / "database" / "tickets.db"))
    return sources


def backup_one(src: Path, dest: Path) -> None:
    """Consistent copy via SQLite's online backup API — safe while src is in use."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    src_conn = sqlite3.connect(f"file:{src.as_posix()}?mode=ro", uri=True)
    try:
        dst_conn = sqlite3.connect(str(dest))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up all simplex_mind databases")
    parser.add_argument("--dest", type=Path, default=REPO_ROOT / "database" / "backups",
                        help="Backup root (default: database/backups/, gitignored)")
    args = parser.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    target = args.dest / stamp
    copied, skipped, failed = [], [], []
    for label, src in _sources():
        if not src.exists():
            skipped.append(label)
            print(f"  skip   {label} (no source at {src})")
            continue
        try:
            backup_one(src, target / label)
            copied.append(label)
            print(f"  backup {label} ({src.stat().st_size // 1024} KiB)")
        except sqlite3.Error as e:
            failed.append(label)
            print(f"  FAIL   {label}: {e}", file=sys.stderr)

    print(f"\n{len(copied)} backed up, {len(skipped)} skipped -> {target}")
    if failed:
        print(f"ERROR {len(failed)} backup(s) failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
