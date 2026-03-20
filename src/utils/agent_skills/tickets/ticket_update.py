"""
Tool: ticket_update.py
Purpose: CLI to update a ticket's status, priority, notes, title, or description

Usage:
    python src/utils/agent_skills/tickets/ticket_update.py --id CORN-001 --status done
    python src/utils/agent_skills/tickets/ticket_update.py --id SHOP-002 --priority high --note "Confirmed on v2"
    python src/utils/agent_skills/tickets/ticket_update.py --id CORN-003 --title "New title"
    python src/utils/agent_skills/tickets/ticket_update.py --id SHOP-005 --target app_test2 --status done

Output:
    OK CORN-001 updated
    { ... ticket JSON ... }
"""

import argparse
import json
import sys

from ticket_db import update_ticket, append_note, get_ticket, VALID_STATUSES, VALID_PRIORITIES


def main():
    parser = argparse.ArgumentParser(description='Update an existing ticket')
    parser.add_argument('--id', required=True, help='Ticket ID (e.g. CORN-001)')
    parser.add_argument('--status', choices=VALID_STATUSES, help='New status')
    parser.add_argument('--priority', choices=VALID_PRIORITIES, help='New priority')
    parser.add_argument('--note', help='Text to append to notes (timestamped)')
    parser.add_argument('--title', help='New title')
    parser.add_argument('--description', help='New description')
    parser.add_argument('--target', default=None,
                        help='Target project (routes to that project\'s ticket DB). '
                             'When omitted, inferred from ticket ID prefix.')

    args = parser.parse_args()

    ticket_id = args.id.upper()

    # Append note first (separate operation to preserve append semantics)
    if args.note:
        note_result = append_note(ticket_id, args.note, target=args.target)
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
        result = update_ticket(ticket_id, target=args.target, **fields)
    elif args.note:
        # note-only update — re-read current state for output
        result = get_ticket(ticket_id, target=args.target)
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
