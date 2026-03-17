"""
Tool: Conversation History Ingester
Purpose: Parse Claude Code JSONL transcripts and ingest verbatim user/assistant text into conversation_history.db

Source directories (scanned in order):
    1. ~/.claude/projects/-home-simplex-projects-simplex_mind/*.jsonl  (new sessions)
    2. ~/.claude/projects/-home-simplex-projects-cornucopia2/*.jsonl   (historical sessions)
    3. Any additional directories passed via --source-dirs

Usage:
    python3 conversation_ingest.py              # ingest new/changed files
    python3 conversation_ingest.py --force      # re-ingest everything
    python3 conversation_ingest.py --dry-run    # preview without writing
    python3 conversation_ingest.py --stats      # show ingestion stats
    python3 conversation_ingest.py --scan-all   # scan all ~/.claude/projects/*/
    python3 conversation_ingest.py --source-dirs /path/one /path/two

Dependencies:
    - conversation_db.py (local)
    - json, glob, os (stdlib)
"""

import json
import glob
import os
import sys
import argparse
from collections import defaultdict
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from conversation_db import get_connection, upsert_session, insert_message, get_ingest_state, set_ingest_state, get_stats

# Default JSONL source directories
DEFAULT_SOURCE_DIRS = [
    Path.home() / ".claude" / "projects" / "-home-simplex-projects-simplex_mind",
    Path.home() / ".claude" / "projects" / "-home-simplex-projects-cornucopia2",
]


def _discover_source_dirs(scan_all: bool = False, extra_dirs: list = None) -> list:
    """Build the list of JSONL source directories to scan."""
    dirs = []

    if scan_all:
        # Scan all ~/.claude/projects/*/
        base = Path.home() / ".claude" / "projects"
        if base.is_dir():
            for d in sorted(base.iterdir()):
                if d.is_dir() and any(d.glob("*.jsonl")):
                    dirs.append(d)
    else:
        dirs = [d for d in DEFAULT_SOURCE_DIRS if d.is_dir()]

    if extra_dirs:
        for d in extra_dirs:
            p = Path(d).expanduser().resolve()
            if p.is_dir() and p not in dirs:
                dirs.append(p)

    return dirs


def extract_text(content) -> str:
    """Extract verbatim text from message content (string or list of blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get('type') == 'text':
                text = block.get('text', '')
                if text:
                    parts.append(text)
        return '\n'.join(parts)
    return ''


def parse_jsonl_file(filepath: str) -> dict:
    """Parse a JSONL file and return grouped messages by session.

    Returns:
        {
            session_id: {
                'slug': str or None,
                'source_file': str,
                'git_branch': str or None,
                'messages': [{uuid, parent_uuid, role, content, timestamp, git_branch}, ...]
            }
        }
    """
    sessions = defaultdict(lambda: {
        'slug': None,
        'source_file': os.path.basename(filepath),
        'git_branch': None,
        'messages': []
    })

    lines_read = 0
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            lines_read += 1
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = obj.get('type')
            if msg_type not in ('user', 'assistant'):
                continue

            # Skip sidechain messages
            if obj.get('isSidechain'):
                continue

            session_id = obj.get('sessionId')
            if not session_id:
                continue

            uuid = obj.get('uuid')
            if not uuid:
                continue

            # Extract slug if present (appears on some messages)
            slug = obj.get('slug')
            if slug:
                sessions[session_id]['slug'] = slug

            # Track git branch
            git_branch = obj.get('gitBranch')
            if git_branch and not sessions[session_id]['git_branch']:
                sessions[session_id]['git_branch'] = git_branch

            # Extract text content
            message = obj.get('message', {})
            content_raw = message.get('content', '') if isinstance(message, dict) else ''

            # Also check for planContent on user messages (plan mode)
            if not content_raw and msg_type == 'user':
                content_raw = obj.get('planContent', '')

            text = extract_text(content_raw)
            if not text or not text.strip():
                continue

            timestamp = obj.get('timestamp', '')
            parent_uuid = obj.get('parentUuid')

            sessions[session_id]['messages'].append({
                'uuid': uuid,
                'parent_uuid': parent_uuid,
                'role': msg_type,
                'content': text,
                'timestamp': timestamp,
                'git_branch': git_branch,
            })

    return dict(sessions), lines_read


def ingest_file(conn, filepath: str, force: bool = False, dry_run: bool = False) -> dict:
    """Ingest a single JSONL file.

    Returns:
        {'skipped': bool, 'sessions': int, 'messages_new': int, 'messages_total': int, 'lines': int}
    """
    fname = os.path.basename(filepath)
    stat = os.stat(filepath)
    file_size = stat.st_size
    file_mtime = stat.st_mtime

    # Check ingest state
    if not force:
        state = get_ingest_state(conn, fname)
        if state and state['file_size'] == file_size and abs(state['file_mtime'] - file_mtime) < 0.01:
            return {'skipped': True, 'sessions': 0, 'messages_new': 0, 'messages_total': 0, 'lines': 0}

    # Parse the file
    sessions_data, lines_read = parse_jsonl_file(filepath)

    if dry_run:
        total_msgs = sum(len(s['messages']) for s in sessions_data.values())
        return {'skipped': False, 'sessions': len(sessions_data), 'messages_new': total_msgs,
                'messages_total': total_msgs, 'lines': lines_read}

    messages_new = 0
    messages_total = 0

    for session_id, sdata in sessions_data.items():
        msgs = sdata['messages']
        if not msgs:
            continue

        # Sort by timestamp, assign sequence numbers
        msgs.sort(key=lambda m: m['timestamp'])
        for i, msg in enumerate(msgs):
            msg['sequence_num'] = i

        # Compute session metadata
        first_ts = msgs[0]['timestamp']
        last_ts = msgs[-1]['timestamp']

        upsert_session(
            conn,
            session_id=session_id,
            slug=sdata['slug'],
            source_file=sdata['source_file'],
            git_branch=sdata['git_branch'],
            first_message_at=first_ts,
            last_message_at=last_ts,
            message_count=len(msgs),
        )

        for msg in msgs:
            messages_total += 1
            before = conn.total_changes
            insert_message(
                conn,
                uuid=msg['uuid'],
                session_id=session_id,
                role=msg['role'],
                content=msg['content'],
                timestamp=msg['timestamp'],
                parent_uuid=msg['parent_uuid'],
                git_branch=msg['git_branch'],
                sequence_num=msg['sequence_num'],
            )
            if conn.total_changes > before:
                messages_new += 1

    # Update ingest state
    set_ingest_state(conn, fname, file_size, file_mtime, lines_read)
    conn.commit()

    return {'skipped': False, 'sessions': len(sessions_data), 'messages_new': messages_new,
            'messages_total': messages_total, 'lines': lines_read}


def run_ingestion(force: bool = False, dry_run: bool = False,
                  scan_all: bool = False, extra_dirs: list = None) -> dict:
    """Ingest all JSONL files from all source directories.

    Returns summary stats.
    """
    source_dirs = _discover_source_dirs(scan_all=scan_all, extra_dirs=extra_dirs)

    if not source_dirs:
        return {'error': 'No source directories found', 'files': 0}

    # Collect all JSONL files from all source dirs
    files = []
    for d in source_dirs:
        files.extend(sorted(glob.glob(str(d / "*.jsonl"))))

    if not files:
        dirs_str = ', '.join(str(d) for d in source_dirs)
        return {'error': f'No JSONL files found in: {dirs_str}', 'files': 0}

    conn = get_connection()

    totals = {
        'source_dirs': [str(d) for d in source_dirs],
        'files_total': len(files),
        'files_processed': 0,
        'files_skipped': 0,
        'sessions_total': 0,
        'messages_new': 0,
        'messages_total': 0,
        'lines_total': 0,
    }

    for filepath in files:
        result = ingest_file(conn, filepath, force=force, dry_run=dry_run)

        if result['skipped']:
            totals['files_skipped'] += 1
        else:
            totals['files_processed'] += 1
            totals['sessions_total'] += result['sessions']
            totals['messages_new'] += result['messages_new']
            totals['messages_total'] += result['messages_total']
            totals['lines_total'] += result['lines']

    if not dry_run:
        conn.commit()
    conn.close()

    return totals


def show_stats():
    """Print ingestion statistics."""
    conn = get_connection()
    stats = get_stats(conn)
    conn.close()

    print("=== Conversation History Stats ===")
    print(f"Sessions:           {stats['total_sessions']}")
    print(f"Messages (total):   {stats['total_messages']}")
    print(f"  User:             {stats['user_messages']}")
    print(f"  Assistant:        {stats['assistant_messages']}")
    print(f"Files ingested:     {stats['files_ingested']}")
    print(f"Earliest session:   {stats['earliest_session']}")
    print(f"Latest session:     {stats['latest_session']}")
    print(f"DB size:            {stats.get('db_size_mb', '?')} MB")


def main():
    parser = argparse.ArgumentParser(description='Ingest Claude Code JSONL transcripts into conversation_history.db')
    parser.add_argument('--force', action='store_true', help='Re-ingest all files regardless of state')
    parser.add_argument('--dry-run', action='store_true', help='Preview what would be ingested without writing')
    parser.add_argument('--stats', action='store_true', help='Show ingestion statistics')
    parser.add_argument('--scan-all', action='store_true', help='Scan all ~/.claude/projects/*/ directories')
    parser.add_argument('--source-dirs', nargs='+', help='Additional JSONL source directories')

    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    mode = "DRY RUN" if args.dry_run else ("FORCE" if args.force else "incremental")
    source_dirs = _discover_source_dirs(scan_all=args.scan_all, extra_dirs=args.source_dirs)
    print(f"Ingestion mode: {mode}")
    print(f"Source dirs: {[str(d) for d in source_dirs]}")

    result = run_ingestion(force=args.force, dry_run=args.dry_run,
                           scan_all=args.scan_all, extra_dirs=args.source_dirs)

    if 'error' in result:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    print(f"\nFiles:    {result['files_processed']} processed, {result['files_skipped']} skipped (of {result['files_total']})")
    print(f"Sessions: {result['sessions_total']}")
    print(f"Messages: {result['messages_new']} new (of {result['messages_total']} seen)")
    print(f"Lines:    {result['lines_total']}")

    if not args.dry_run and result['files_processed'] > 0:
        print("\nPost-ingest stats:")
        show_stats()


if __name__ == "__main__":
    main()
