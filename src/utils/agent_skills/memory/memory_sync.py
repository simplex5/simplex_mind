"""
Tool: Memory Sync — MEMORY.md Auto-Sync Block
Purpose: Maintains an auto-generated block inside database/memory/MEMORY.md
         sourced from memory.db, WITHOUT touching hand-curated content.

MEMORY.md is hand-curated (per CLAUDE.md Memory Protocol). This tool owns
exactly one region of the file, delimited by marker comments:

    <!-- BEGIN AUTO-SYNC (memory_sync.py) — edits inside this block are overwritten -->
    ...generated sections...
    <!-- END AUTO-SYNC -->

On sync: everything outside the markers is preserved verbatim. If the block
exists it is replaced in place; otherwise it is appended to the end of the
file. If MEMORY.md doesn't exist, a minimal file is created.

Usage:
    python src/utils/agent_skills/memory/memory_sync.py            # sync block
    python src/utils/agent_skills/memory/memory_sync.py --dry-run  # preview

Dependencies:
    - sqlite3 (stdlib)
    - pathlib (stdlib)

Output:
    Updated MEMORY.md (or preview to stdout with --dry-run)
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

# Auto-sync block markers — everything between them belongs to this tool
BLOCK_BEGIN = "<!-- BEGIN AUTO-SYNC (memory_sync.py) — edits inside this block are overwritten -->"
BLOCK_END = "<!-- END AUTO-SYNC -->"

# Import memory_db functions
try:
    from .memory_db import list_entries
except ImportError:
    try:
        from memory_db import list_entries
    except ImportError:
        def list_entries(**kwargs):
            return {"success": False, "entries": []}


# Tags that identify automated run metrics (excluded from insight section)
AUTOMATED_INSIGHT_TAGS = {'run', 'metrics'}


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
    """Format a decision entry."""
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
    """Format a generic entry."""
    content = entry.get('content', '')
    importance = entry.get('importance', 5)
    return f"- [imp:{importance}] {content}"


def generate_auto_block() -> str:
    """Generate the auto-sync block content from memory.db."""
    parts = []
    parts.append(BLOCK_BEGIN)
    parts.append(f"## Auto-Synced from memory.db — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # Decisions
    result = list_entries(entry_type='decision', min_importance=1, limit=50)
    decisions = result.get('entries', []) if result.get('success') else []
    parts.append("### Decisions\n")
    if decisions:
        for entry in decisions:
            parts.append(_format_decision(entry))
    else:
        parts.append("*No decisions recorded yet.*")
    parts.append("")

    # High-importance facts (skip noisy rolling-average entries)
    result = list_entries(entry_type='fact', min_importance=6, limit=30)
    facts = result.get('entries', []) if result.get('success') else []
    facts = [f for f in facts if 'rolling average' not in f.get('content', '').lower()]
    parts.append("### Key Facts (importance ≥ 6)\n")
    if facts:
        for entry in facts:
            parts.append(_format_entry(entry))
    else:
        parts.append("*No high-importance facts recorded.*")
    parts.append("")

    # Insights (manual only — exclude automated run metrics)
    result = list_entries(entry_type='insight', min_importance=1, limit=50)
    all_insights = result.get('entries', []) if result.get('success') else []
    manual_insights = [e for e in all_insights if not _is_automated_insight(e)]
    parts.append("### Insights\n")
    if manual_insights:
        for entry in manual_insights:
            parts.append(_format_entry(entry))
    else:
        parts.append("*No manual insights recorded.*")
    parts.append("")

    # Events (recent, high importance)
    result = list_entries(entry_type='event', min_importance=6, limit=20)
    events = result.get('entries', []) if result.get('success') else []
    if events:
        parts.append("### Events\n")
        for entry in events:
            created = entry.get('created_at', '')[:10]
            parts.append(f"- [{created}] {entry.get('content', '')}")
        parts.append("")

    parts.append(BLOCK_END)
    return '\n'.join(parts)


def merge_block_into_file(existing: str, block: str) -> str:
    """Replace the auto-sync block in existing content, or append it.

    Everything outside the markers is preserved verbatim.
    """
    begin_idx = existing.find(BLOCK_BEGIN)
    end_idx = existing.find(BLOCK_END)

    if begin_idx != -1 and end_idx != -1 and end_idx > begin_idx:
        before = existing[:begin_idx].rstrip('\n')
        after = existing[end_idx + len(BLOCK_END):].lstrip('\n')
        merged = before + '\n\n' + block
        if after:
            merged += '\n\n' + after
        return merged.rstrip('\n') + '\n'

    # No block yet — append at end
    return existing.rstrip('\n') + '\n\n' + block + '\n'


def sync(dry_run: bool = False) -> Dict[str, Any]:
    """
    Sync the auto-generated block into MEMORY.md, preserving curated content.

    Args:
        dry_run: If True, print the merged result without writing.

    Returns:
        dict with success status
    """
    block = generate_auto_block()

    if MEMORY_FILE.exists():
        existing = MEMORY_FILE.read_text(encoding='utf-8')
        content = merge_block_into_file(existing, block)
    else:
        content = (
            "# Persistent Memory\n\n"
            "> Curated long-term facts and preferences. Edit freely — only the\n"
            "> AUTO-SYNC block below is machine-managed.\n\n"
            + block + '\n'
        )

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
        "message": f"MEMORY.md auto-sync block updated ({line_count} lines total; curated content preserved)"
    }


def main():
    parser = argparse.ArgumentParser(
        description='Memory Sync — update the auto-sync block in MEMORY.md from memory.db')
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
