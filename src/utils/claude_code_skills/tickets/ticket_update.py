"""
Tool: ticket_update.py
Purpose: CLI to update a ticket's status, priority, notes, title, or description

Usage:
    python src/utils/claude_code_skills/tickets/ticket_update.py --id PROJECT-001 --status done
    python src/utils/claude_code_skills/tickets/ticket_update.py --id PROJECT-002 --priority high --note "Confirmed on v2"
    python src/utils/claude_code_skills/tickets/ticket_update.py --id PROJECT-003 --title "New title"

Output:
    OK PROJECT-001 updated
    { ... ticket JSON ... }
"""

import argparse
import json
import sys

from ticket_db import update_ticket, append_note, VALID_STATUSES, VALID_PRIORITIES


def main():
    parser = argparse.ArgumentParser(description='Update an existing ticket')
    parser.add_argument('--id', required=True, help='Ticket ID (e.g. PROJECT-001)')
    parser.add_argument('--status', choices=VALID_STATUSES, help='New status')
    parser.add_argument('--priority', choices=VALID_PRIORITIES, help='New priority')
    parser.add_argument('--note', help='Text to append to notes (timestamped)')
    parser.add_argument('--title', help='New title')
    parser.add_argument('--description', help='New description')

    args = parser.parse_args()

    ticket_id = args.id.upper()

    # Append note first (separate operation to preserve append semantics)
    if args.note:
        note_result = append_note(ticket_id, args.note)
        if not note_result.get('success'):
            print(f"ERROR {note_result.get('error')}")
            sys.exit(1)

    # Collect field updates
    fields = {}
    if args.status:
        fields['status'] = args.status
    if args.priority:
        fields['priority'] = args.priority
    if args.title:
        fields['title'] = args.title
    if args.description:
        fields['description'] = args.description

    if fields:
        result = update_ticket(ticket_id, **fields)
    elif args.note:
        # note-only update — re-read current state for output
        from ticket_db import get_ticket
        result = get_ticket(ticket_id)
        result['id'] = ticket_id
    else:
        print("ERROR No fields to update. Provide --status, --priority, --note, --title, or --description.")
        sys.exit(1)

    if result.get('success'):
        print(f"OK {ticket_id} updated")
    else:
        print(f"ERROR {result.get('error')}")
        sys.exit(1)

    print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
