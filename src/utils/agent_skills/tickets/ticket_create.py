"""
Tool: ticket_create.py
Purpose: CLI to create a new ticket in database/tickets.db

Usage:
    python src/utils/agent_skills/tickets/ticket_create.py \
        --type bug \
        --title "Canvas flickers on resize" \
        --project myproject \
        --priority high \
        --description "Observed during gameplay: canvas redraws incorrectly after window resize." \
        --how-discovered "Spotted during debug session"

Output:
    OK PROJECT-001 created
    { ... ticket JSON ... }
"""

import argparse
import json
import sys

from ticket_db import create_ticket, VALID_TYPES, VALID_PRIORITIES


def main():
    parser = argparse.ArgumentParser(description='Create a new ticket')
    parser.add_argument('--type', required=True, choices=VALID_TYPES, dest='ticket_type',
                        help='Ticket type')
    parser.add_argument('--title', required=True, help='Short summary')
    parser.add_argument('--description', default='', help='Full description')
    parser.add_argument('--project', default='global',
                        help='Project name')
    parser.add_argument('--priority', default='medium', choices=VALID_PRIORITIES,
                        help='Priority level')
    parser.add_argument('--how-discovered', default='manually logged',
                        dest='how_discovered',
                        help='Context for how this was found')

    args = parser.parse_args()

    result = create_ticket(
        ticket_type=args.ticket_type,
        title=args.title,
        description=args.description,
        project=args.project,
        how_discovered=args.how_discovered,
        priority=args.priority,
    )

    if result.get('success'):
        print(f"OK {result['id']} created")
    else:
        print(f"ERROR {result.get('error')}")
        sys.exit(1)

    print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
