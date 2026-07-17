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
import logging
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List

log = logging.getLogger(__name__)

# Paths
try:
    from .._common import REPO_ROOT as PROJECT_ROOT
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from _common import REPO_ROOT as PROJECT_ROOT
MEMORY_DIR = PROJECT_ROOT / "database" / "memory"
SYSTEMS_FILE = MEMORY_DIR / "systems.md"

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
    except Exception as e:
        log.warning("digest: ticket section unavailable (%s)", e)
        return {"count": 0, "critical": [], "high": [], "in_progress": []}


def _get_recent_decisions(days: int = 14) -> List[Dict[str, Any]]:
    """Get decision entries from the last N days."""
    try:
        result = list_entries(entry_type='decision', min_importance=1, limit=20)
        if not result.get('success'):
            return []

        # created_at is UTC 'YYYY-MM-DD HH:MM:SS' (CURRENT_TIMESTAMP) — match it
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        return [
            e for e in result.get('entries', [])
            if e.get('created_at', '') >= cutoff
        ]
    except Exception as e:
        log.warning("digest: recent-decisions section unavailable (%s)", e)
        return []


def _get_active_systems_summary() -> List[str]:
    """Get one-line summaries from systems.md Active Systems section.

    systems.md entries are prose paragraphs under ###/#### headings — take
    each heading plus the first non-empty line beneath it as the summary.
    """
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

        if line.startswith('### ') or line.startswith('#### '):
            current_name = line.lstrip('#').strip()
        elif current_name and line.strip() and not line.strip().startswith('*'):
            first_line = line.strip()
            # Legacy '- **Purpose:**' bullets stay supported
            if first_line.startswith('- **Purpose:**'):
                first_line = first_line.replace('- **Purpose:** ', '')
            if len(first_line) > 120:
                first_line = first_line[:117] + '...'
            summaries.append(f"- **{current_name}**: {first_line}")
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
    except Exception as e:
        log.warning("digest: git log unavailable (%s)", e)
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
    except Exception as e:
        log.warning("digest: git branch unavailable (%s)", e)
    return "unknown"


def _get_subconscious_status() -> List[str]:
    """Autotune state summary + index staleness. Empty list = section omitted.
    The staleness check runs even when no autotune state file exists yet."""
    lines = []
    state_path = PROJECT_ROOT / 'database' / 'memory' / 'subconscious_autotune_state.json'
    try:
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding='utf-8'))
            err = state.get('last_run_error')
            if err:
                lines.append(f"AUTOTUNE CRON FAILED [{str(err.get('at', ''))[:10]}]: "
                             f"{err.get('error', 'unknown')} — check logs/subconscious_autotune.log")
            if state.get('last_run'):
                lines.append(f"Autotune last run: {state['last_run'][:10]} — "
                             f"{state.get('last_run_summary', '')}")
            pending = state.get('pending', [])
            if pending:
                lines.append(f"PENDING KEYWORD CANDIDATES: {len(pending)} — propose them to the "
                             f"user (subconscious_autotune.py --review, then --approve/--reject)")
    except Exception as e:
        log.warning("digest: autotune state unreadable (%s)", e)
    lines.extend(_check_subconscious_index_staleness())
    return lines


def _check_subconscious_index_staleness() -> List[str]:
    """Warn when pieces/keyword-overlay were edited after the index was built —
    the recall hook would silently serve stale text (SIMP-L1-028)."""
    index_path = PROJECT_ROOT / 'database' / 'memory' / 'subconscious_index.json'
    pieces_dir = PROJECT_ROOT / 'subconscious'
    overlay = PROJECT_ROOT / 'database' / 'memory' / 'subconscious_keywords.json'
    try:
        if not index_path.exists():
            if pieces_dir.exists() and any(pieces_dir.glob('*.md')):
                return ["SUBCONSCIOUS INDEX MISSING — run subconscious_index.py to build it"]
            return []
        built_at = json.loads(index_path.read_text(encoding='utf-8')).get('built_at', '')
        built = datetime.fromisoformat(built_at).timestamp()
        sources = list(pieces_dir.glob('*.md')) if pieces_dir.exists() else []
        if overlay.exists():
            sources.append(overlay)
        newest = max((f.stat().st_mtime for f in sources), default=0)
        if newest > built:
            return ["SUBCONSCIOUS INDEX STALE — pieces/keywords edited after last build; "
                    "run subconscious_index.py to refresh"]
    except Exception as e:
        log.warning("digest: subconscious staleness check failed (%s)", e)
    return []


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

    # 5. Subconscious autotune — only when there is something to act on
    sub = _get_subconscious_status()
    if sub:
        parts.append("## Subconscious")
        for line in sub:
            parts.append(line)
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
