"""
Tool: ticket_read.py
Purpose: CLI to read a single ticket in full detail

Usage:
    python src/utils/claude_code_skills/tickets/ticket_read.py --id PROJECT-001

Output:
    Formatted ticket detail block + JSON
"""

import argparse
import json
import sys

from ticket_db import get_ticket


def format_ticket(t: dict) -> str:
    lines = [
        f"{'='*60}",
        f"  {t.get('id')}  [{t.get('ticket_type','').upper()}]  {t.get('status','').upper()}  priority:{t.get('priority','')}",
        f"{'='*60}",
        f"Title:    {t.get('title','')}",
        f"Project:  {t.get('project','')}",
        f"Created:  {t.get('created_at','')}",
        f"Updated:  {t.get('updated_at','')}",
    ]
    if t.get('resolved_at'):
        lines.append(f"Resolved: {t.get('resolved_at')}")
    lines.append('')
    lines.append('Description:')
    lines.append(t.get('description', '(none)') or '(none)')
    lines.append('')
    lines.append('How discovered:')
    lines.append(t.get('how_discovered', '') or '(not specified)')
    notes = t.get('notes', '')
    if notes:
        lines.append('')
        lines.append('Notes:')
        lines.append(notes)
    lines.append(f"{'='*60}")
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Read a single ticket')
    parser.add_argument('--id', required=True, help='Ticket ID (e.g. PROJECT-001)')

    args = parser.parse_args()
    ticket_id = args.id.upper()

    result = get_ticket(ticket_id)

    if not result.get('success'):
        print(f"ERROR {result.get('error')}")
        sys.exit(1)

    print(format_ticket(result['ticket']))
    print()
    print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
