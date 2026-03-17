"""
Tool: Memory Sync — MEMORY.md Auto-Regeneration
Purpose: Regenerates database/memory/MEMORY.md from structured data in memory.db

Replaces manual MEMORY.md curation with automated aggregation from the database.
Preserves a ## Pinned section at the top for items that must always appear.

Usage:
    python src/utils/agent_skills/memory/memory_sync.py            # regenerate
    python src/utils/agent_skills/memory/memory_sync.py --dry-run  # preview

Dependencies:
    - sqlite3 (stdlib)
    - pathlib (stdlib)

Output:
    Regenerated MEMORY.md file (or preview to stdout with --dry-run)
"""

import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# Paths
MEMORY_DIR = (Path(__file__).parent.parent.parent.parent.parent / "database" / "memory").resolve()
MEMORY_FILE = MEMORY_DIR / "MEMORY.md"

# Import memory_db functions
try:
    from .memory_db import list_entries, VALID_TYPES
except ImportError:
    try:
        from memory_db import list_entries, VALID_TYPES
    except ImportError:
        def list_entries(**kwargs):
            return {"success": False, "entries": []}
        VALID_TYPES = []


# Tags that identify automated run metrics (excluded from insight section)
AUTOMATED_INSIGHT_TAGS = {'run', 'metrics'}


def _read_pinned_section() -> str:
    """Read the ## Pinned section from existing MEMORY.md, if present."""
    if not MEMORY_FILE.exists():
        return ""

    content = MEMORY_FILE.read_text(encoding='utf-8')
    lines = content.split('\n')
    pinned_lines = []
    in_pinned = False

    for line in lines:
        if line.strip() == '## Pinned':
            in_pinned = True
            pinned_lines.append(line)
            continue
        if in_pinned:
            if line.startswith('## '):
                break
            pinned_lines.append(line)

    return '\n'.join(pinned_lines).strip() if pinned_lines else ""


def _is_automated_insight(entry: Dict[str, Any]) -> bool:
    """Check if an entry is an automated run metrics insight."""
    tags_raw = entry.get('tags')
    if not tags_raw:
        return False
    try:
        tags = json.loads(tags_raw) if isinstance(tags_raw, str) else tags_raw
    except (json.JSONDecodeError, TypeError):
        return False
    return AUTOMATED_INSIGHT_TAGS.issubset(set(tags))


def _format_decision(entry: Dict[str, Any]) -> str:
    """Format a decision entry for MEMORY.md."""
    content = entry.get('content', '')
    created = entry.get('created_at', '')[:10]
    tags_raw = entry.get('tags')
    tags = []
    if tags_raw:
        try:
            tags = json.loads(tags_raw) if isinstance(tags_raw, str) else tags_raw
        except (json.JSONDecodeError, TypeError):
            pass
    tag_str = f" ({', '.join(tags)})" if tags else ""
    return f"- [{created}]{tag_str} {content}"


def _format_entry(entry: Dict[str, Any]) -> str:
    """Format a generic entry for MEMORY.md."""
    content = entry.get('content', '')
    importance = entry.get('importance', 5)
    return f"- [imp:{importance}] {content}"


def generate_memory_md() -> str:
    """Generate MEMORY.md content from memory.db."""
    parts = []

    # Header
    parts.append("# Persistent Memory\n")
    parts.append("> Auto-generated from memory.db by memory_sync.py.")
    parts.append(f"> Last synced: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    parts.append("> Edit the ## Pinned section directly. All other sections are regenerated.\n")

    # Pinned section (preserved from existing file)
    pinned = _read_pinned_section()
    if pinned:
        parts.append(pinned)
    else:
        parts.append("## Pinned\n")
        parts.append("- simplex_mind is the brain repo — project-agnostic tools and databases")
        parts.append("- Projects are registered in projects.yaml")
    parts.append("")

    # Decisions section
    result = list_entries(entry_type='decision', min_importance=1, limit=50)
    decisions = result.get('entries', []) if result.get('success') else []
    parts.append("## Decisions\n")
    if decisions:
        for entry in decisions:
            parts.append(_format_decision(entry))
    else:
        parts.append("*No decisions recorded yet.*")
    parts.append("")

    # Facts section (importance >= 6, skip noisy rolling-average entries)
    result = list_entries(entry_type='fact', min_importance=6, limit=30)
    facts = result.get('entries', []) if result.get('success') else []
    # Filter out model-performance rolling averages (they are noisy)
    facts = [f for f in facts if 'rolling average' not in f.get('content', '').lower()]
    parts.append("## Key Facts\n")
    if facts:
        for entry in facts:
            parts.append(_format_entry(entry))
    else:
        parts.append("*No high-importance facts recorded.*")
    parts.append("")

    # Insights section (manual only — exclude automated run metrics)
    result = list_entries(entry_type='insight', min_importance=1, limit=50)
    all_insights = result.get('entries', []) if result.get('success') else []
    manual_insights = [e for e in all_insights if not _is_automated_insight(e)]
    parts.append("## Insights\n")
    if manual_insights:
        for entry in manual_insights:
            parts.append(_format_entry(entry))
    else:
        parts.append("*No manual insights recorded. Automated run metrics are excluded from this section.*")
    parts.append("")

    # Events section (recent, high importance)
    result = list_entries(entry_type='event', min_importance=6, limit=20)
    events = result.get('entries', []) if result.get('success') else []
    if events:
        parts.append("## Events\n")
        for entry in events:
            created = entry.get('created_at', '')[:10]
            parts.append(f"- [{created}] {entry.get('content', '')}")
        parts.append("")

    # Footer
    parts.append("---\n")
    parts.append(f"*Last updated: {datetime.now().strftime('%Y-%m-%d')}*")
    parts.append("*Auto-generated by memory_sync.py — do not edit sections other than ## Pinned.*")

    return '\n'.join(parts)


def sync(dry_run: bool = False) -> Dict[str, Any]:
    """
    Regenerate MEMORY.md from memory.db.

    Args:
        dry_run: If True, print output without writing file

    Returns:
        dict with success status
    """
    content = generate_memory_md()
    line_count = len(content.split('\n'))

    if dry_run:
        print(content)
        return {
            "success": True,
            "dry_run": True,
            "lines": line_count,
            "message": f"Preview: {line_count} lines (not written)"
        }

    MEMORY_FILE.write_text(content, encoding='utf-8')
    return {
        "success": True,
        "path": str(MEMORY_FILE),
        "lines": line_count,
        "message": f"MEMORY.md regenerated ({line_count} lines)"
    }


def main():
    parser = argparse.ArgumentParser(description='Memory Sync — regenerate MEMORY.md from memory.db')
    parser.add_argument('--dry-run', action='store_true', help='Preview output without writing')
    args = parser.parse_args()

    result = sync(dry_run=args.dry_run)

    if result.get('success'):
        if not args.dry_run:
            print(f"OK {result.get('message')}")
    else:
        print(f"ERROR {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
