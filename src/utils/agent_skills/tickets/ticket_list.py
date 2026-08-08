"""
Tool: ticket_list.py
Purpose: CLI to list and filter tickets from per-project ticket databases

Usage:
    python src/utils/agent_skills/tickets/ticket_list.py               # open tickets from active project
    python src/utils/agent_skills/tickets/ticket_list.py --all         # all statuses
    python src/utils/agent_skills/tickets/ticket_list.py --status done
    python src/utils/agent_skills/tickets/ticket_list.py --project myproject --priority high
    python src/utils/agent_skills/tickets/ticket_list.py --type bug --limit 20
    python src/utils/agent_skills/tickets/ticket_list.py --target other-project
    python src/utils/agent_skills/tickets/ticket_list.py --all-projects
    python src/utils/agent_skills/tickets/ticket_list.py --all --limit 0   # every row of a plain listing
    python src/utils/agent_skills/tickets/ticket_list.py --json            # machine output
    python src/utils/agent_skills/tickets/ticket_list.py --query "campfire" # LIKE search, title+description;
                                                                           # all statuses + unlimited by default

Output:
    Formatted table to stdout; full JSON block only with --json.
    A truncation banner is printed as the FIRST line whenever the limit cut rows off.
    With --query, titles print unclipped and tickets whose match lives only in the
    description get a context line between the table and the count line.
"""

import argparse
import json
import sys

from ticket_db import list_tickets, list_tickets_all, VALID_STATUSES, VALID_TYPES, VALID_PRIORITIES


def format_table(tickets: list, clip_titles: bool = True) -> str:
    if not tickets:
        return "(no tickets)"

    headers = ['ID', 'Type', 'Status', 'Priority', 'Project', 'Title']
    col_widths = [len(h) for h in headers]

    rows = []
    for t in tickets:
        # Titles are stored unsanitized; a newline would break the one-line-per-row
        # table, so collapse in both modes.
        title = t.get('title', '').replace('\n', ' ')
        row = [
            t.get('id', ''),
            t.get('ticket_type', ''),
            t.get('status', ''),
            t.get('priority', ''),
            t.get('project', ''),
            title[:60] if clip_titles else title,
        ]
        rows.append(row)
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    def fmt_row(cells):
        return '  '.join(c.ljust(col_widths[i]) for i, c in enumerate(cells))

    separator = '  '.join('-' * w for w in col_widths)
    lines = [fmt_row(headers), separator]
    for row in rows:
        lines.append(fmt_row(row))
    return '\n'.join(lines)


def match_context(query: str, tickets: list) -> list:
    """One '  ID: ...snippet...' line per ticket whose match lives only in the
    description. Searches the RAW query (the SQL-escaped pattern would never
    match itself, e.g. a query containing a literal %)."""
    lines = []
    q = query.lower()
    for t in tickets:
        if q in t.get('title', '').lower():
            continue
        desc = t.get('description') or ''
        pos = desc.lower().find(q)
        if pos < 0:
            # SQLite LIKE matched but Python's find didn't (casefold divergence)
            # — the row's presence in the table is the answer; skip the snippet.
            continue
        start = max(0, pos - 60)
        end = min(len(desc), pos + len(q) + 60)
        snippet = desc[start:end].replace('\n', ' ')
        prefix = '...' if start > 0 else ''
        suffix = '...' if end < len(desc) else ''
        lines.append(f"  {t.get('id', '')}: {prefix}{snippet}{suffix}")
    return lines


def main():
    parser = argparse.ArgumentParser(description='List tickets')
    parser.add_argument('--status', choices=VALID_STATUSES, help='Filter by status')
    parser.add_argument('--type', choices=VALID_TYPES, dest='ticket_type', help='Filter by type')
    parser.add_argument('--project', help='Filter by project')
    parser.add_argument('--priority', choices=VALID_PRIORITIES, help='Filter by priority')
    parser.add_argument('--limit', type=int, default=None,
                        help='Max results (default: 50, or unlimited with --query; 0 = no limit)')
    parser.add_argument('--all', action='store_true', dest='show_all',
                        help='Show all statuses (not just open)')
    parser.add_argument('--query', default=None,
                        help='Case-insensitive substring search over title + description. '
                             'Searches all statuses and returns every match unless '
                             '--status / --limit are given explicitly.')
    parser.add_argument('--json', action='store_true', dest='emit_json',
                        help='Also print the full JSON result block (machine output)')
    parser.add_argument('--target', default=None,
                        help='Target project (routes to that project\'s ticket DB). '
                             'Defaults to active project.')
    parser.add_argument('--all-projects', action='store_true', dest='all_projects',
                        help='List tickets from ALL project databases')

    args = parser.parse_args()

    # Query mode is a duplicate check: unless overridden explicitly, it searches
    # every status (a duplicate may be closed) with no row cap.
    limit = args.limit if args.limit is not None else (0 if args.query else 50)
    show_all = args.show_all or (args.query is not None and args.status is None)

    if args.all_projects:
        result = list_tickets_all(
            status=args.status,
            ticket_type=args.ticket_type,
            project=args.project,
            priority=args.priority,
            limit=limit,
            show_all=show_all,
            query=args.query,
        )
    else:
        result = list_tickets(
            status=args.status,
            ticket_type=args.ticket_type,
            project=args.project,
            priority=args.priority,
            limit=limit,
            show_all=show_all,
            query=args.query,
            target=args.target,
        )

    if not result.get('success'):
        print(f"ERROR {result.get('error')}")
        sys.exit(1)

    tickets = result.get('tickets', [])
    total = result.get('total', 0)

    if len(tickets) < total:
        print(f"!! TRUNCATED: showing {len(tickets)} of {total} - "
              f"pass --limit N (0 = all); --json for machine output !!")
    print(format_table(tickets, clip_titles=args.query is None))
    if args.query:
        for line in match_context(args.query, tickets):
            print(line)
    print(f"\n{len(tickets)} of {total} ticket(s) shown")
    if args.emit_json:
        print()
        print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
