"""
Tool: Conversation Purge — delete stored transcripts by project, age, or session
Purpose: Gives the verbatim conversation store a real retention/deletion story
         (SIMP-D2-026, PRIVACY.md).

Usage:
    python conversation_purge.py --older-than 90 --dry-run
    python conversation_purge.py --project my-project --yes
    python conversation_purge.py --session <uuid> --yes
    python conversation_purge.py --all --yes --with-usage --vacuum

Semantics:
    - At least one selector required: --project (sessions recorded on that
      project's simplex_mind branch), --older-than <days> (by last_message_at),
      --session <id>, --all. Selectors combine with AND.
    - Deletes matched sessions' messages (the messages_ad trigger keeps the
      FTS index consistent) and tombstones the session rows (message_count=0)
      so stats keep their shape.
    - message_usage is PRESERVED by default — token accounting is designed to
      survive transcript cleanup. --with-usage deletes usage rows and drops
      the tombstoned session rows entirely.
    - ingest_state is untouched: recorded byte offsets prevent purged content
      from silently re-ingesting from still-existing source JSONL files. The
      upstream copies under ~/.claude/projects/ must be removed separately
      (see PRIVACY.md).
    - Non-interactive confirmation: without --yes the matched summary is
      printed and exit code is 1 — no stdin prompts (agents can't answer them).
      --dry-run always deletes nothing and exits 0.
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from .._common import cli_finish
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from _common import cli_finish

try:
    from .conversation_db import get_connection
except ImportError:
    try:
        from conversation_db import get_connection
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from conversation_db import get_connection

try:
    from .. import project_resolver
except ImportError:
    import project_resolver


def _match_sessions(conn, args):
    """Return list of (session_id, message_count, last_message_at) matching the selectors."""
    where, params = [], []
    if args.project:
        proj = project_resolver.get_project(args.project)
        if not proj:
            raise ValueError(f"unknown project '{args.project}' — not registered in projects.yaml")
        if not proj.get("branch"):
            raise ValueError(f"project '{args.project}' has no branch: in projects.yaml")
        where.append("git_branch = ?")
        params.append(proj["branch"])
    if args.older_than is not None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=args.older_than)
                  ).strftime("%Y-%m-%dT%H:%M:%SZ")
        where.append("last_message_at < ?")
        params.append(cutoff)
    if args.session:
        where.append("session_id = ?")
        params.append(args.session)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        f"SELECT session_id, message_count, last_message_at FROM sessions {clause}",
        params).fetchall()
    return [tuple(r) for r in rows]


def purge(args) -> dict:
    conn = get_connection()
    try:
        matched = _match_sessions(conn, args)
        ids = [m[0] for m in matched]
        placeholders = ",".join("?" * len(ids))
        n_messages = 0
        n_bytes = 0
        if ids:
            n_messages, n_bytes = conn.execute(
                f"SELECT COUNT(*), COALESCE(SUM(LENGTH(content)), 0) FROM messages "
                f"WHERE session_id IN ({placeholders})", ids).fetchone()
        n_usage = 0
        if ids and args.with_usage:
            (n_usage,) = conn.execute(
                f"SELECT COUNT(*) FROM message_usage WHERE session_id IN ({placeholders})",
                ids).fetchone()

        result = {
            "success": True,
            "matched_sessions": len(ids),
            "matched_messages": n_messages,
            "matched_bytes": n_bytes,
            "usage_rows": n_usage if args.with_usage else "preserved",
            "deleted": False,
        }

        if args.dry_run:
            result["message"] = "dry run — nothing deleted"
            return result
        if not args.yes:
            result["success"] = False
            result["error"] = (
                f"refusing to delete {len(ids)} session(s) / {n_messages} message(s) "
                f"without --yes (re-run with --yes to delete, --dry-run to preview)")
            return result
        if not ids:
            result["message"] = "no sessions matched — nothing deleted"
            return result

        # messages_ad trigger removes the FTS rows for each deleted message
        conn.execute(f"DELETE FROM messages WHERE session_id IN ({placeholders})", ids)
        if args.with_usage:
            conn.execute(f"DELETE FROM message_usage WHERE session_id IN ({placeholders})", ids)
            conn.execute(f"DELETE FROM sessions WHERE session_id IN ({placeholders})", ids)
        else:
            conn.execute(
                f"UPDATE sessions SET message_count = 0, "
                f"updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') "
                f"WHERE session_id IN ({placeholders})", ids)
        conn.commit()
        if args.vacuum:
            conn.execute("VACUUM")
        result["deleted"] = True
        result["message"] = (
            f"purged {n_messages} message(s) from {len(ids)} session(s)"
            + (f", {n_usage} usage row(s)" if args.with_usage else ", token usage preserved"))
        return result
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Delete stored conversation transcripts (see PRIVACY.md)")
    parser.add_argument("--project", help="Limit to sessions recorded on this project's branch")
    parser.add_argument("--older-than", type=int, metavar="DAYS",
                        help="Limit to sessions whose last message is older than DAYS days")
    parser.add_argument("--session", help="Limit to one session ID")
    parser.add_argument("--all", action="store_true", help="Select every session")
    parser.add_argument("--dry-run", action="store_true", help="Print matches, delete nothing")
    parser.add_argument("--yes", action="store_true",
                        help="Actually delete (without it: print summary, exit 1)")
    parser.add_argument("--with-usage", action="store_true",
                        help="Also delete token-usage rows and session rows (default preserves them)")
    parser.add_argument("--vacuum", action="store_true", help="VACUUM the DB after deleting")
    args = parser.parse_args()

    if not (args.project or args.older_than is not None or args.session or args.all):
        parser.error("pick a selector: --project, --older-than, --session, or --all")

    try:
        result = purge(args)
    except ValueError as e:
        result = {"success": False, "error": str(e)}
    cli_finish(result)


if __name__ == "__main__":
    main()
