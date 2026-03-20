"""
Tool: Session Digest — Focused Session-Start Context
Purpose: Produces a concise context digest (< 200 lines) for session start

Unlike memory_read.py which dumps everything, this produces focused output:
1. Open tickets — count + critical/high items
2. Recent decisions — last 14 days
3. Active systems summary — one line per system
4. In-progress work — tickets with status=in_progress
5. Recent git — last 5 commits on current branch

Usage:
    python src/utils/agent_skills/memory/session_digest.py

Dependencies:
    - sqlite3 (stdlib)
    - subprocess (stdlib)
    - pathlib (stdlib)

Output:
    Markdown digest to stdout (< 200 lines)
"""

import sys
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

# Paths
PROJECT_ROOT = (Path(__file__).parent.parent.parent.parent.parent).resolve()
MEMORY_DIR = PROJECT_ROOT / "database" / "memory"
SYSTEMS_FILE = MEMORY_DIR / "systems.md"
TICKETS_DB = PROJECT_ROOT / "database" / "tickets.db"

# Import memory_db
try:
    from .memory_db import list_entries, get_connection
except ImportError:
    try:
        from memory_db import list_entries, get_connection
    except ImportError:
        def list_entries(**kwargs):
            return {"success": False, "entries": []}
        def get_connection():
            return None

# Import ticket_db and project_resolver
_ticket_list = None
_get_active = None
try:
    from ..tickets.ticket_db import list_tickets as _ticket_list
    from ..project_resolver import get_active_project as _get_active
except ImportError:
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "tickets"))
        from ticket_db import list_tickets as _ticket_list
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from project_resolver import get_active_project as _get_active
    except ImportError:
        pass


def _get_open_tickets() -> Dict[str, Any]:
    """Get open ticket summary."""
    if not _ticket_list:
        return {"count": 0, "critical": [], "high": [], "in_progress": []}

    try:
        # Route to active project's ticket DB
        active_target = None
        if _get_active:
            active = _get_active()
            if active:
                active_target = active["name"]

        result = _ticket_list(status='open', target=active_target)
        tickets = result.get('tickets', []) if result.get('success') else []

        ip_result = _ticket_list(status='in_progress', target=active_target)
        ip_tickets = ip_result.get('tickets', []) if ip_result.get('success') else []

        critical = [t for t in tickets if t.get('priority') == 'critical']
        high = [t for t in tickets if t.get('priority') == 'high']

        return {
            "count": len(tickets),
            "critical": critical,
            "high": high,
            "in_progress": ip_tickets
        }
    except Exception:
        return {"count": 0, "critical": [], "high": [], "in_progress": []}


def _get_recent_decisions(days: int = 14) -> List[Dict[str, Any]]:
    """Get decision entries from the last N days."""
    try:
        result = list_entries(entry_type='decision', min_importance=1, limit=20)
        if not result.get('success'):
            return []

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        return [
            e for e in result.get('entries', [])
            if e.get('created_at', '') >= cutoff
        ]
    except Exception:
        return []


def _get_active_systems_summary() -> List[str]:
    """Get one-line summaries from systems.md Active Systems section."""
    if not SYSTEMS_FILE.exists():
        return []

    content = SYSTEMS_FILE.read_text(encoding='utf-8')
    lines = content.split('\n')
    summaries = []
    in_active = False
    current_name = None

    for line in lines:
        if line.strip() == '## Active Systems':
            in_active = True
            continue
        if line.startswith('## ') and in_active:
            break
        if not in_active:
            continue

        if line.startswith('### '):
            current_name = line[4:].strip()
        elif line.strip().startswith('- **Purpose:**') and current_name:
            purpose = line.strip().replace('- **Purpose:** ', '')
            summaries.append(f"- **{current_name}**: {purpose}")
            current_name = None

    return summaries


def _get_recent_git(count: int = 5) -> List[str]:
    """Get last N git commits on current branch."""
    try:
        result = subprocess.run(
            ['git', 'log', f'-{count}', '--oneline', '--no-decorate'],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
            timeout=5
        )
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
    except Exception:
        pass
    return []


def _get_current_branch() -> str:
    """Get current git branch name."""
    try:
        result = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def generate_digest() -> str:
    """Generate the session digest."""
    parts = []
    parts.append(f"# Session Digest — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    parts.append(f"Branch: `{_get_current_branch()}`\n")

    # 1. Open tickets
    tickets = _get_open_tickets()
    parts.append("## Tickets")
    parts.append(f"Open: {tickets['count']}")
    if tickets['critical']:
        for t in tickets['critical']:
            parts.append(f"  CRITICAL: {t.get('id')} — {t.get('title')}")
    if tickets['high']:
        for t in tickets['high']:
            parts.append(f"  HIGH: {t.get('id')} — {t.get('title')}")
    if tickets['in_progress']:
        parts.append("In progress:")
        for t in tickets['in_progress']:
            parts.append(f"  {t.get('id')} — {t.get('title')}")
    parts.append("")

    # 2. Recent decisions
    decisions = _get_recent_decisions()
    if decisions:
        parts.append("## Recent Decisions (14d)")
        for d in decisions:
            created = d.get('created_at', '')[:10]
            content = d.get('content', '')
            # Truncate long entries
            if len(content) > 150:
                content = content[:147] + '...'
            parts.append(f"- [{created}] {content}")
        parts.append("")

    # 3. Active systems summary
    systems = _get_active_systems_summary()
    if systems:
        parts.append("## Active Systems")
        for s in systems:
            parts.append(s)
        parts.append("")

    # 4. Recent git
    commits = _get_recent_git()
    if commits:
        parts.append("## Recent Commits")
        for c in commits:
            parts.append(f"- {c}")
        parts.append("")

    return '\n'.join(parts)


def main():
    digest = generate_digest()
    line_count = len(digest.split('\n'))

    if line_count > 200:
        # Trim to keep under 200 lines
        lines = digest.split('\n')[:200]
        lines.append("\n*[truncated — digest exceeded 200 lines]*")
        digest = '\n'.join(lines)

    print(digest)


if __name__ == "__main__":
    main()
