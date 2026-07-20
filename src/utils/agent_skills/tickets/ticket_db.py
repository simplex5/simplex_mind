"""
Tool: Ticket Database Manager
Purpose: SQLite CRUD operations for persistent ticket tracking (JIRA-like)

Schema:
- tickets: id (PREFIX-<MACHINE>-NNN, e.g. SIMP-L1-042; NNN is zero-padded to a
           3-digit minimum and keeps counting past 999), type, status, priority,
           title, description, project, how_discovered, created_at, updated_at,
           resolved_at, notes
- ticket_counter: auto-increment counter for ID generation

The MACHINE segment (top-level `machine:` key in projects.yaml, e.g. L1/D1)
keeps IDs unique across machines — each machine has its own local ticket DBs
and counter, so without it two machines mint colliding IDs.

Per-project databases: each project gets its own tickets.db at
<project_path>/database/tickets.db with its own prefix and counter.
Prefix is resolved from projects.yaml via project_resolver.

Usage (via CLI tools — not called directly):
    from ticket_db import create_ticket, update_ticket, get_ticket, list_tickets, append_note
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import project_resolver (handle both relative and sys.path import)
try:
    from ..project_resolver import (
        get_ticket_db_path,
        get_ticket_prefix,
        get_all_projects,
        get_active_project,
        infer_project_from_prefix,
        get_machine_id,
    )
    from .._common import row_to_dict, PRIORITY_ORDER, PRIORITY_SQL_CASE, utc_now_db, run_migrations
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from project_resolver import (
        get_ticket_db_path,
        get_ticket_prefix,
        get_all_projects,
        get_active_project,
        infer_project_from_prefix,
        get_machine_id,
    )
    from _common import row_to_dict, PRIORITY_ORDER, PRIORITY_SQL_CASE, utc_now_db, run_migrations

VALID_TYPES = ['bug', 'feature', 'task', 'improvement', 'documentation']
VALID_STATUSES = ['open', 'in_progress', 'blocked', 'done', 'wont_fix']
VALID_PRIORITIES = ['low', 'medium', 'high', 'critical']


def get_connection(db_path: Path = None, target: str = None) -> sqlite3.Connection:
    """Get database connection with row_factory, creating tables if needed.

    Args:
        db_path: Explicit path to database file. Takes priority over target.
        target: Project name to resolve DB path from projects.yaml.
                If both are None, resolves from active project.
    """
    if db_path is None:
        db_path = get_ticket_db_path(target)
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Apply ordered schema migrations (PRAGMA user_version gated)."""
    run_migrations(conn, MIGRATIONS)


def _migration_1_base_schema(conn: sqlite3.Connection) -> None:
    """v1: base schema. Idempotent — pre-versioning DBs replay this as a no-op."""
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

    # Seed counter row if absent
    cursor.execute('INSERT OR IGNORE INTO ticket_counter (id, next_num) VALUES (1, 1)')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tickets_type ON tickets(ticket_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tickets_project ON tickets(project)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority)')

    conn.commit()


MIGRATIONS = [
    (1, _migration_1_base_schema),
]


def _next_id(cursor: sqlite3.Cursor, prefix: str) -> str:
    """Atomically increment counter and return PREFIX-<MACHINE>-NNN id."""
    machine = get_machine_id()
    if not machine:
        raise RuntimeError(
            "No machine id configured — add a top-level `machine: <ID>` key to "
            "projects.yaml (e.g. `machine: L1` for laptop 1, `machine: D1` for "
            "desktop 1). Ticket IDs embed it so machines never mint colliding IDs."
        )
    cursor.execute('UPDATE ticket_counter SET next_num = next_num + 1 WHERE id = 1')
    cursor.execute('SELECT next_num - 1 AS num FROM ticket_counter WHERE id = 1')
    num = cursor.fetchone()['num']
    return f"{prefix}-{machine}-{num:03d}"


def _resolve_target_for_id(ticket_id: str, target: str = None) -> str:
    """Resolve target project from ticket ID prefix when target is not explicit."""
    if target:
        return target
    inferred = infer_project_from_prefix(ticket_id)
    return inferred  # May be None — will fall through to active project


def create_ticket(
    ticket_type: str,
    title: str,
    description: str = '',
    project: str = None,
    how_discovered: str = 'manually logged',
    priority: str = 'medium',
    target: str = None,
) -> Dict[str, Any]:
    """
    Create a new ticket.

    Args:
        project: Metadata label. If None, defaults to the routed project name
                 (explicit target, else active project, else 'global').
        target: Project name to route to. If None, uses active project.

    Returns:
        {"success": True, "id": "PREFIX-NNN", "ticket": {...}}
    """
    if ticket_type not in VALID_TYPES:
        return {"success": False, "error": f"Invalid type. Must be one of: {VALID_TYPES}"}
    if priority not in VALID_PRIORITIES:
        return {"success": False, "error": f"Invalid priority. Must be one of: {VALID_PRIORITIES}"}

    try:
        prefix = get_ticket_prefix(target)
        conn = get_connection(target=target)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    # Default the project label to wherever the ticket is actually routed,
    # so the column stays consistent with the DB it lands in.
    if not project:
        if target:
            project = target
        else:
            active = get_active_project()
            project = active["name"] if active else "global"

    cursor = conn.cursor()

    ticket_id = _next_id(cursor, prefix)

    cursor.execute('''
        INSERT INTO tickets (id, ticket_type, title, description, project, how_discovered, priority)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (ticket_id, ticket_type, title, description, project, how_discovered, priority))

    conn.commit()

    cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,))
    ticket = row_to_dict(cursor.fetchone())
    conn.close()

    return {"success": True, "id": ticket_id, "ticket": ticket}


def update_ticket(ticket_id: str, target: str = None, **fields) -> Dict[str, Any]:
    """
    Update any subset of mutable fields on a ticket.

    Mutable fields: status, priority, title, description, project, how_discovered, notes
    Sets updated_at automatically. Sets resolved_at when status becomes done/wont_fix.

    Args:
        target: Project name. If None, inferred from ticket ID prefix.
    """
    mutable = {'status', 'priority', 'title', 'description', 'project', 'how_discovered', 'notes'}

    resolved_target = _resolve_target_for_id(ticket_id, target)
    try:
        conn = get_connection(target=resolved_target)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,))
    if not cursor.fetchone():
        conn.close()
        return {"success": False, "error": f"Ticket {ticket_id} not found"}

    updates = []
    values = []

    for field, value in fields.items():
        if field not in mutable:
            continue
        if field == 'status' and value not in VALID_STATUSES:
            conn.close()
            return {"success": False, "error": f"Invalid status. Must be one of: {VALID_STATUSES}"}
        if field == 'priority' and value not in VALID_PRIORITIES:
            conn.close()
            return {"success": False, "error": f"Invalid priority. Must be one of: {VALID_PRIORITIES}"}
        updates.append(f'{field} = ?')
        values.append(value)

    if not updates:
        conn.close()
        return {"success": False, "error": "No valid fields to update"}

    updates.append('updated_at = ?')
    values.append(utc_now_db())

    # Set resolved_at when closing; clear it when reopening
    new_status = fields.get('status')
    if new_status in ('done', 'wont_fix'):
        updates.append('resolved_at = ?')
        values.append(utc_now_db())
    elif new_status in ('open', 'in_progress', 'blocked'):
        updates.append('resolved_at = NULL')

    values.append(ticket_id)
    cursor.execute(f'UPDATE tickets SET {", ".join(updates)} WHERE id = ?', values)
    conn.commit()

    cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,))
    ticket = row_to_dict(cursor.fetchone())
    conn.close()

    return {"success": True, "id": ticket_id, "ticket": ticket}


def get_ticket(ticket_id: str, target: str = None) -> Dict[str, Any]:
    """Fetch a single ticket by ID.

    Args:
        target: Project name. If None, inferred from ticket ID prefix.
    """
    resolved_target = _resolve_target_for_id(ticket_id, target)
    try:
        conn = get_connection(target=resolved_target)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,))
    ticket = row_to_dict(cursor.fetchone())
    conn.close()

    if not ticket:
        return {"success": False, "error": f"Ticket {ticket_id} not found"}
    return {"success": True, "ticket": ticket}


def list_tickets(
    status: Optional[str] = None,
    ticket_type: Optional[str] = None,
    project: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 50,
    show_all: bool = False,
    target: str = None,
) -> Dict[str, Any]:
    """
    List tickets with optional filters.

    If show_all is False and status is None, defaults to open tickets only.

    Args:
        target: Project name to list from. If None, uses active project.
    """
    try:
        conn = get_connection(target=target)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    cursor = conn.cursor()

    conditions = []
    params: List[Any] = []

    if not show_all:
        if status:
            if status not in VALID_STATUSES:
                conn.close()
                return {"success": False, "error": f"Invalid status. Must be one of: {VALID_STATUSES}"}
            conditions.append('status = ?')
            params.append(status)
        else:
            conditions.append('status = ?')
            params.append('open')
    elif status:
        if status not in VALID_STATUSES:
            conn.close()
            return {"success": False, "error": f"Invalid status. Must be one of: {VALID_STATUSES}"}
        conditions.append('status = ?')
        params.append(status)

    if ticket_type:
        if ticket_type not in VALID_TYPES:
            conn.close()
            return {"success": False, "error": f"Invalid type. Must be one of: {VALID_TYPES}"}
        conditions.append('ticket_type = ?')
        params.append(ticket_type)

    if project:
        conditions.append('project = ?')
        params.append(project)

    if priority:
        if priority not in VALID_PRIORITIES:
            conn.close()
            return {"success": False, "error": f"Invalid priority. Must be one of: {VALID_PRIORITIES}"}
        conditions.append('priority = ?')
        params.append(priority)

    where = ' AND '.join(conditions) if conditions else '1=1'

    cursor.execute(f'''
        SELECT * FROM tickets
        WHERE {where}
        ORDER BY {PRIORITY_SQL_CASE}, created_at ASC
        LIMIT ?
    ''', params + [limit])

    tickets = [row_to_dict(row) for row in cursor.fetchall()]

    cursor.execute(f'SELECT COUNT(*) AS count FROM tickets WHERE {where}', params)
    total = cursor.fetchone()['count']

    conn.close()
    return {"success": True, "tickets": tickets, "total": total, "limit": limit}


def list_tickets_all(
    status: Optional[str] = None,
    ticket_type: Optional[str] = None,
    project: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 50,
    show_all: bool = False,
) -> Dict[str, Any]:
    """
    List tickets across ALL project databases, merged and sorted.
    """
    all_tickets = []
    total = 0

    for proj in get_all_projects():
        db_path = Path(proj["path"]) / "database" / "tickets.db"
        if not db_path.exists():
            continue
        result = list_tickets(
            status=status,
            ticket_type=ticket_type,
            project=project,
            priority=priority,
            limit=limit,
            show_all=show_all,
            target=proj["name"],
        )
        if result.get("success"):
            all_tickets.extend(result.get("tickets", []))
            total += result.get("total", 0)

    # Sort merged results by priority then date
    all_tickets.sort(key=lambda t: (
        PRIORITY_ORDER.get(t.get('priority', 'low'), 4),
        t.get('created_at', ''),
    ))

    # Apply limit to merged results
    if len(all_tickets) > limit:
        all_tickets = all_tickets[:limit]

    return {"success": True, "tickets": all_tickets, "total": total, "limit": limit}


def append_note(ticket_id: str, note: str, target: str = None) -> Dict[str, Any]:
    """Append a timestamped note to the ticket's notes field.

    Args:
        target: Project name. If None, inferred from ticket ID prefix.
    """
    resolved_target = _resolve_target_for_id(ticket_id, target)
    try:
        conn = get_connection(target=resolved_target)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    cursor = conn.cursor()

    cursor.execute('SELECT notes FROM tickets WHERE id = ?', (ticket_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": f"Ticket {ticket_id} not found"}

    timestamp = utc_now_db()
    existing = row['notes'] or ''
    separator = '\n\n' if existing else ''
    new_notes = f"{existing}{separator}[{timestamp}] {note}"

    cursor.execute('''
        UPDATE tickets SET notes = ?, updated_at = ?
        WHERE id = ?
    ''', (new_notes, timestamp, ticket_id))
    conn.commit()

    cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,))
    ticket = row_to_dict(cursor.fetchone())
    conn.close()

    return {"success": True, "id": ticket_id, "ticket": ticket}
