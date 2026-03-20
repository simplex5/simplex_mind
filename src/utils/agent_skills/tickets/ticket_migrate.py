#!/usr/bin/env python3
"""
Tool: ticket_migrate.py
Purpose: One-time migration from shared tickets.db to per-project ticket databases.

What it does:
1. Reads shared DB (simplex_mind/database/tickets.db)
2. Routes tickets by project field using projects.yaml config
3. Re-IDs tickets whose prefix doesn't match their target project
4. Sets each project's counter to max_ticket_number + 1
5. Backs up shared DB as tickets.db.bak
6. Prints migration report

Usage:
    python3 src/utils/agent_skills/tickets/ticket_migrate.py
    python3 src/utils/agent_skills/tickets/ticket_migrate.py --dry-run
"""

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT / "src" / "utils" / "agent_skills"))

from project_resolver import get_all_projects

SHARED_DB = _PROJECT_ROOT / "database" / "tickets.db"


def build_targets() -> dict:
    """Build target routing from projects.yaml via project_resolver."""
    targets = {}
    for proj in get_all_projects():
        name = proj["name"]
        targets[name] = {
            "db_path": Path(proj["path"]) / "database" / "tickets.db",
            "prefix": proj["ticket_prefix"],
            "projects": {name},
        }
    return targets


def init_db(conn: sqlite3.Connection) -> None:
    """Create ticket tables if they don't exist."""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            ticket_type TEXT NOT NULL CHECK(ticket_type IN ('bug', 'feature', 'task', 'improvement', 'documentation')),
            status TEXT DEFAULT 'open' CHECK(status IN ('open', 'in_progress', 'blocked', 'done', 'wont_fix')),
            priority TEXT DEFAULT 'medium' CHECK(priority IN ('low', 'medium', 'high', 'critical')),
            title TEXT NOT NULL,
            description TEXT,
            project TEXT DEFAULT 'global',
            how_discovered TEXT DEFAULT 'manually logged',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT,
            notes TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_counter (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            next_num INTEGER DEFAULT 1
        )
    ''')
    cursor.execute('INSERT OR IGNORE INTO ticket_counter (id, next_num) VALUES (1, 1)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tickets_type ON tickets(ticket_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tickets_project ON tickets(project)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority)')
    conn.commit()


def get_ticket_num(ticket_id: str) -> int:
    """Extract numeric part from ticket ID."""
    return int(ticket_id.split("-", 1)[1])


def read_shared_db() -> list:
    """Read all tickets from the shared database."""
    conn = sqlite3.connect(str(SHARED_DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM tickets ORDER BY id")
    tickets = [dict(row) for row in cur.fetchall()]
    conn.close()
    return tickets


def route_ticket(ticket: dict, targets: dict) -> str:
    """Determine which target DB a ticket belongs to."""
    project = ticket.get("project", "global")
    for target_name, cfg in targets.items():
        if project in cfg["projects"]:
            return target_name
    # Fallback to simplex_mind for unknown projects
    return "simplex_mind"


def needs_re_id(ticket: dict, target_name: str, targets: dict) -> bool:
    """Check if a ticket needs its ID changed to match the target prefix."""
    expected_prefix = targets[target_name]["prefix"]
    current_prefix = ticket["id"].split("-", 1)[0]
    return current_prefix != expected_prefix


def migrate(dry_run: bool = False):
    """Run the migration."""
    targets = build_targets()

    print(f"{'DRY RUN — ' if dry_run else ''}Per-Project Ticket Migration")
    print("=" * 60)

    # Read all shared tickets
    tickets = read_shared_db()
    print(f"\nShared DB: {len(tickets)} tickets")

    # Route tickets to targets
    routed = {}
    for target_name in targets:
        routed[target_name] = []

    for ticket in tickets:
        target = route_ticket(ticket, targets)
        routed[target].append(ticket)

    for target_name, tix in routed.items():
        print(f"  → {target_name}: {len(tix)} tickets")

    # Process each target
    report = []

    for target_name, cfg in targets.items():
        target_tickets = routed.get(target_name, [])
        if not target_tickets:
            continue

        db_path = cfg["db_path"]
        prefix = cfg["prefix"]
        print(f"\n--- {target_name} ({prefix}) → {db_path} ---")

        # For simplex_mind, we'll clear and rebuild (it IS the shared DB)
        # For others, we insert missing tickets
        if target_name == "simplex_mind":
            existing_ids = set()
        else:
            existing_ids = set()
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT id FROM tickets")
                existing_ids = {row["id"] for row in cur.fetchall()}
                conn.close()
                print(f"  Existing: {len(existing_ids)} tickets")

        # Determine re-IDs and inserts
        re_ids = []
        inserts = []
        skips = []
        max_num = 0

        for ticket in target_tickets:
            old_id = ticket["id"]

            if needs_re_id(ticket, target_name, targets):
                re_ids.append((old_id, ticket))
            else:
                num = get_ticket_num(old_id)
                max_num = max(max_num, num)
                if old_id in existing_ids:
                    skips.append(old_id)
                else:
                    inserts.append(ticket)

        # Assign new IDs for re-IDed tickets
        next_re_id_num = max_num + 1
        re_id_map = {}
        for old_id, ticket in re_ids:
            new_id = f"{prefix}-{next_re_id_num:03d}"
            re_id_map[old_id] = new_id
            ticket["id"] = new_id
            inserts.append(ticket)
            max_num = max(max_num, next_re_id_num)
            next_re_id_num += 1

        counter_value = max_num + 1

        print(f"  Skip (already exists): {len(skips)}")
        print(f"  Insert: {len(inserts)}")
        print(f"  Re-ID: {len(re_ids)}")
        for old_id, new_id in re_id_map.items():
            print(f"    {old_id} → {new_id}")
        print(f"  Counter → {counter_value}")

        if dry_run:
            report.append({
                "target": target_name,
                "skips": len(skips),
                "inserts": len(inserts),
                "re_ids": re_id_map,
                "counter": counter_value,
            })
            continue

        # Execute writes
        db_path.parent.mkdir(parents=True, exist_ok=True)

        if target_name == "simplex_mind":
            backup_path = SHARED_DB.with_suffix(".db.bak")
            shutil.copy2(str(SHARED_DB), str(backup_path))
            print(f"  Backed up → {backup_path}")

            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            init_db(conn)
            cur = conn.cursor()
            cur.execute("DELETE FROM tickets")
            conn.commit()
        else:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            init_db(conn)
            cur = conn.cursor()

        # Insert tickets
        for ticket in inserts:
            try:
                cur.execute('''
                    INSERT OR IGNORE INTO tickets
                    (id, ticket_type, status, priority, title, description,
                     project, how_discovered, created_at, updated_at, resolved_at, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    ticket["id"], ticket["ticket_type"], ticket["status"],
                    ticket["priority"], ticket["title"], ticket["description"],
                    ticket["project"], ticket["how_discovered"],
                    ticket["created_at"], ticket["updated_at"],
                    ticket["resolved_at"], ticket["notes"],
                ))
            except sqlite3.IntegrityError as e:
                print(f"  WARN: Could not insert {ticket['id']}: {e}")

        # Set counter
        cur.execute("UPDATE ticket_counter SET next_num = ? WHERE id = 1", (counter_value,))
        conn.commit()
        conn.close()

        report.append({
            "target": target_name,
            "skips": len(skips),
            "inserts": len(inserts),
            "re_ids": re_id_map,
            "counter": counter_value,
        })

    # Print summary
    print("\n" + "=" * 60)
    print("MIGRATION REPORT")
    print("=" * 60)
    for r in report:
        print(f"\n{r['target']}:")
        print(f"  Inserted: {r['inserts']}")
        print(f"  Skipped:  {r['skips']}")
        print(f"  Re-IDed:  {len(r['re_ids'])}")
        if r["re_ids"]:
            for old, new in r["re_ids"].items():
                print(f"    {old} → {new}")
        print(f"  Counter:  {r['counter']}")

    if dry_run:
        print("\n⚠ DRY RUN — no changes made")
    else:
        print("\n✓ Migration complete")


def main():
    parser = argparse.ArgumentParser(description="Migrate shared tickets.db to per-project databases")
    parser.add_argument("--dry-run", action="store_true", help="Preview migration without making changes")
    args = parser.parse_args()
    migrate(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
