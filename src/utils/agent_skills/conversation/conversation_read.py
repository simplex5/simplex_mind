"""
Tool: Conversation History Reader
Purpose: Query and display conversation history from conversation_history.db

Usage:
    python3 conversation_read.py --action list-sessions [--limit N] [--search SLUG]
    python3 conversation_read.py --action get-session --session-id UUID
    python3 conversation_read.py --action search --query "..." [--session-id UUID] [--role user|assistant]
    python3 conversation_read.py --action stats
    python3 conversation_read.py --action recent [--hours N]

Dependencies:
    - conversation_db.py (local)
"""

import json
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from conversation_db import get_connection, get_session, list_sessions, get_session_messages, search_messages, get_stats


def format_timestamp(iso_ts: str) -> str:
    """Format ISO timestamp to compact display form."""
    if not iso_ts:
        return "?"
    try:
        dt = datetime.fromisoformat(iso_ts.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M')
    except (ValueError, AttributeError):
        return iso_ts[:16]


def format_time_only(iso_ts: str) -> str:
    """Format ISO timestamp to HH:MM:SS only."""
    if not iso_ts:
        return "?"
    try:
        dt = datetime.fromisoformat(iso_ts.replace('Z', '+00:00'))
        return dt.strftime('%H:%M:%S')
    except (ValueError, AttributeError):
        return iso_ts[11:19] if len(iso_ts) > 19 else iso_ts


def action_list_sessions(args):
    """List sessions with metadata."""
    conn = get_connection()
    sessions = list_sessions(conn, limit=args.limit, search=args.search)
    conn.close()

    if not sessions:
        print("No sessions found.")
        return

    # Header
    print(f"{'SLUG':<35} {'BRANCH':<45} {'PERIOD':<35} {'MSGS':>5}")
    print("-" * 125)

    for s in sessions:
        slug = s['slug'] or s['session_id'][:12]
        branch = (s['git_branch'] or '')[:44]
        first = format_timestamp(s['first_message_at'])
        last = format_timestamp(s['last_message_at'])
        period = f"{first} -> {last}"
        count = s['message_count']
        print(f"{slug:<35} {branch:<45} {period:<35} {count:>5}")

    print(f"\n{len(sessions)} session(s) shown")


def action_get_session(args):
    """Display a full session transcript."""
    if not args.session_id:
        print("ERROR: --session-id required")
        sys.exit(1)

    conn = get_connection()
    session = get_session(conn, args.session_id)

    if not session:
        # Try slug search
        sessions = list_sessions(conn, search=args.session_id, limit=1)
        if sessions:
            session = sessions[0]
            args.session_id = session['session_id']
        else:
            print(f"Session not found: {args.session_id}")
            conn.close()
            sys.exit(1)

    messages = get_session_messages(conn, args.session_id)
    conn.close()

    slug = session['slug'] or session['session_id'][:12]
    branch = session['git_branch'] or '?'
    first = format_timestamp(session['first_message_at'])
    last = format_timestamp(session['last_message_at'])
    count = session['message_count']

    print(f"=== Session: {slug} ===")
    print(f"ID:     {session['session_id']}")
    print(f"Branch: {branch}")
    print(f"Period: {first} -> {last} | Messages: {count}")
    print()

    for msg in messages:
        role = msg['role'].upper()
        ts = format_time_only(msg['timestamp'])
        content = msg['content']

        # Truncate very long messages for display
        if len(content) > 5000:
            content = content[:5000] + f"\n... [{len(content) - 5000} chars truncated]"

        print(f"[{role} {ts}]")
        print(content)
        print()


def action_search(args):
    """Full-text search across messages."""
    if not args.query:
        print("ERROR: --query required")
        sys.exit(1)

    conn = get_connection()
    results = search_messages(
        conn,
        query=args.query,
        session_id=args.session_id,
        role=args.role,
        limit=args.limit
    )
    conn.close()

    if not results:
        print(f"No results for: {args.query}")
        return

    print(f"=== Search: \"{args.query}\" ({len(results)} results) ===\n")

    for msg in results:
        role = msg['role'].upper()
        ts = format_timestamp(msg['timestamp'])
        session = msg['session_id'][:12]
        snippet = msg.get('snippet', msg['content'][:200])

        print(f"[{role} {ts}] session:{session}")
        print(f"  {snippet}")
        print()


def action_stats(args):
    """Show database statistics."""
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


def action_recent(args):
    """Show messages from the last N hours."""
    hours = args.hours or 24
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M:%SZ')

    conn = get_connection()
    cursor = conn.execute('''
        SELECT m.*, s.slug FROM messages m
        JOIN sessions s ON m.session_id = s.session_id
        WHERE m.timestamp >= ?
        ORDER BY m.timestamp DESC
        LIMIT ?
    ''', (cutoff, args.limit))
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not messages:
        print(f"No messages in the last {hours} hours.")
        return

    print(f"=== Last {hours} hours ({len(messages)} messages) ===\n")

    for msg in reversed(messages):
        role = msg['role'].upper()
        ts = format_time_only(msg['timestamp'])
        slug = msg.get('slug', msg['session_id'][:12])
        content = msg['content']
        if len(content) > 300:
            content = content[:300] + "..."

        print(f"[{role} {ts}] {slug}")
        print(f"  {content}")
        print()


def main():
    parser = argparse.ArgumentParser(description='Query conversation history')
    parser.add_argument('--action', required=True,
                        choices=['list-sessions', 'get-session', 'search', 'stats', 'recent'],
                        help='Action to perform')
    parser.add_argument('--session-id', help='Session UUID or slug')
    parser.add_argument('--query', help='Search query')
    parser.add_argument('--role', choices=['user', 'assistant'], help='Filter by role')
    parser.add_argument('--limit', type=int, default=50, help='Max results')
    parser.add_argument('--search', help='Search sessions by slug')
    parser.add_argument('--hours', type=int, default=24, help='Hours for recent action')

    args = parser.parse_args()

    actions = {
        'list-sessions': action_list_sessions,
        'get-session': action_get_session,
        'search': action_search,
        'stats': action_stats,
        'recent': action_recent,
    }

    actions[args.action](args)


if __name__ == "__main__":
    main()
