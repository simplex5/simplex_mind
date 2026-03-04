"""
Tool: ticket_list.py
Purpose: CLI to list and filter tickets from database/tickets.db

Usage:
    python src/utils/agent_skills/tickets/ticket_list.py               # open tickets (default)
    python src/utils/agent_skills/tickets/ticket_list.py --all         # all statuses
    python src/utils/agent_skills/tickets/ticket_list.py --status done
    python src/utils/agent_skills/tickets/ticket_list.py --project myproject --priority high
    python src/utils/agent_skills/tickets/ticket_list.py --type bug --limit 20

Output:
    Formatted table to stdout + JSON block
"""

import argparse
import json
import sys

from ticket_db import list_tickets, VALID_STATUSES, VALID_TYPES, VALID_PRIORITIES

# Priority sort order for display
PRIORITY_ORDER = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}


def format_table(tickets: list) -> str:
    if not tickets:
        return "(no tickets)"

    headers = ['ID', 'Type', 'Status', 'Priority', 'Project', 'Title']
    col_widths = [len(h) for h in headers]

    rows = []
    for t in tickets:
        row = [
            t.get('id', ''),
            t.get('ticket_type', ''),
            t.get('status', ''),
            t.get('priority', ''),
            t.get('project', ''),
            t.get('title', '')[:60],
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


def main():
    parser = argparse.ArgumentParser(description='List tickets')
    parser.add_argument('--status', choices=VALID_STATUSES, help='Filter by status')
    parser.add_argument('--type', choices=VALID_TYPES, dest='ticket_type', help='Filter by type')
    parser.add_argument('--project', help='Filter by project')
    parser.add_argument('--priority', choices=VALID_PRIORITIES, help='Filter by priority')
    parser.add_argument('--limit', type=int, default=50, help='Max results (default: 50)')
    parser.add_argument('--all', action='store_true', dest='show_all',
                        help='Show all statuses (not just open)')

    args = parser.parse_args()

    result = list_tickets(
        status=args.status,
        ticket_type=args.ticket_type,
        project=args.project,
        priority=args.priority,
        limit=args.limit,
        show_all=args.show_all,
    )

    if not result.get('success'):
        print(f"ERROR {result.get('error')}")
        sys.exit(1)

    tickets = result.get('tickets', [])
    total = result.get('total', 0)

    print(format_table(tickets))
    print(f"\n{len(tickets)} of {total} ticket(s) shown")
    print()
    print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
