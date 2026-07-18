"""
Tool: Ticket Renumber (one-off migration, kept for reference like ticket_migrate.py)
Purpose: Migrate existing ticket IDs from the legacy PREFIX-NNN format to the
         machine-scoped PREFIX-<MACHINE>-NNN format (e.g. SIMP-008 -> SIMP-L1-008).

Ticket DBs and counters are per-machine, so two machines independently mint
SIMP-008 for different work. Embedding the machine id (top-level `machine:` key
in projects.yaml) makes IDs globally unique. This tool inserts the machine
segment into every legacy ID on THIS machine, keeping the numbers:

- every project ticket DB (from projects.yaml + the simplex_mind brain DB):
  tickets.id and any legacy IDs referenced inside tickets.notes
- memory.db memory_entries: tags (JSON text), content, context
- daily logs: database/memory/logs/*.md

Idempotent: only IDs matching ^PREFIX-NNN$ are rewritten; already-migrated
three-part IDs are untouched. Counters are numeric-only and unchanged.

Usage:
    python3 ticket_renumber.py --dry-run   # preview the old->new mapping
    python3 ticket_renumber.py             # apply
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from project_resolver import get_all_projects, get_machine_id  # noqa: E402

try:
    from .._common import REPO_ROOT as _REPO_ROOT
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from _common import REPO_ROOT as _REPO_ROOT
_MEMORY_DB = _REPO_ROOT / "database" / "memory" / "memory.db"
_LOGS_DIR = _REPO_ROOT / "database" / "memory" / "logs"


def build_mapping(machine: str) -> dict:
    """Scan every project ticket DB for legacy IDs. Returns
    {db_path_str: {old_id: new_id}} covering all projects."""
    mapping = {}
    for proj in get_all_projects():
        db_path = Path(proj["path"]) / "database" / "tickets.db"
        if not db_path.exists():
            continue
        legacy = re.compile(rf"^{re.escape(proj['ticket_prefix'])}-(\d+)$")
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            ids = [r[0] for r in conn.execute("SELECT id FROM tickets ORDER BY id")]
        finally:
            conn.close()
        db_map = {}
        for tid in ids:
            m = legacy.match(tid)
            if m:
                db_map[tid] = f"{proj['ticket_prefix']}-{machine}-{m.group(1)}"
        if db_map:
            mapping[str(db_path)] = db_map
    return mapping


def rewrite_text(text: str, flat_map: dict) -> str:
    """Replace every legacy ID (word-bounded) in free text."""
    for old, new in flat_map.items():
        text = re.sub(rf"\b{re.escape(old)}\b", new, text)
    return text


def migrate(dry_run: bool = False) -> int:
    machine = get_machine_id()
    if not machine:
        print("ERROR: no top-level `machine:` key in projects.yaml — set it first "
              "(e.g. `machine: L1`).")
        return 1

    mapping = build_mapping(machine)
    flat_map = {old: new for db_map in mapping.values() for old, new in db_map.items()}
    if not flat_map:
        print("Nothing to do — no legacy PREFIX-NNN ids found.")
        return 0

    print(f"Machine id: {machine}")
    for db_path, db_map in mapping.items():
        print(f"\n{db_path}:")
        for old, new in sorted(db_map.items()):
            print(f"  {old}  ->  {new}")

    if dry_run:
        print("\nDRY RUN — nothing written.")
        return 0

    # 1. Ticket DBs: ids + cross-references inside notes
    for db_path, db_map in mapping.items():
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            for old, new in db_map.items():
                cur.execute("UPDATE tickets SET id = ? WHERE id = ?", (new, old))
            for tid, notes in cur.execute(
                    "SELECT id, notes FROM tickets WHERE notes IS NOT NULL").fetchall():
                updated = rewrite_text(notes, flat_map)
                if updated != notes:
                    cur.execute("UPDATE tickets SET notes = ? WHERE id = ?", (updated, tid))
            conn.commit()
        finally:
            conn.close()
        print(f"Updated {db_path}")

    # 2. memory.db: tags JSON + free text
    if not _MEMORY_DB.exists():
        print(f"WARNING: memory DB not found at {_MEMORY_DB} — skipped")
    if _MEMORY_DB.exists():
        conn = sqlite3.connect(str(_MEMORY_DB))
        try:
            cur = conn.cursor()
            rows = cur.execute(
                "SELECT id, tags, content, context FROM memory_entries").fetchall()
            changed = 0
            for row_id, tags, content, context in rows:
                new_vals = {}
                for col, val in (("tags", tags), ("content", content), ("context", context)):
                    if val:
                        updated = rewrite_text(val, flat_map)
                        if updated != val:
                            new_vals[col] = updated
                if new_vals:
                    sets = ", ".join(f"{c} = ?" for c in new_vals)
                    cur.execute(f"UPDATE memory_entries SET {sets} WHERE id = ?",
                                (*new_vals.values(), row_id))
                    changed += 1
            conn.commit()
        finally:
            conn.close()
        print(f"Updated memory.db ({changed} entries)")

    # 3. Daily logs
    if _LOGS_DIR.exists():
        for log in sorted(_LOGS_DIR.glob("*.md")):
            text = log.read_text(encoding="utf-8")
            updated = rewrite_text(text, flat_map)
            if updated != text:
                log.write_text(updated, encoding="utf-8")
                print(f"Updated {log}")

    print(f"\nDone — {len(flat_map)} ticket id(s) migrated to machine '{machine}'.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate ticket IDs to PREFIX-<MACHINE>-NNN")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()
    sys.exit(migrate(dry_run=args.dry_run))
