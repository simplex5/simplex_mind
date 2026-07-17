"""
Tool: ticket_create.py
Purpose: CLI to create a new ticket in the per-project ticket database

Usage:
    python src/utils/agent_skills/tickets/ticket_create.py \
        --type bug \
        --title "Canvas flickers on resize" \
        --project myproject \
        --priority high \
        --description "Observed during gameplay: canvas redraws incorrectly after window resize." \
        --how-discovered "Spotted during debug session" \
        --target other-project

Output:
    OK PROJ-001 created
    { ... ticket JSON ... }
"""

import argparse

from ticket_db import create_ticket, VALID_TYPES, VALID_PRIORITIES
try:
    from .._common import cli_finish
except ImportError:
    from _common import cli_finish  # ticket_db import above put agent_skills on sys.path


def main():
    parser = argparse.ArgumentParser(description='Create a new ticket')
    parser.add_argument('--type', required=True, choices=VALID_TYPES, dest='ticket_type',
                        help='Ticket type')
    parser.add_argument('--title', required=True, help='Short summary')
    parser.add_argument('--description', default='', help='Full description')
    parser.add_argument('--project', default=None,
                        help='Project name (metadata field). Defaults to the '
                             'routed project (target/active), or "global" on the brain DB.')
    parser.add_argument('--priority', default='medium', choices=VALID_PRIORITIES,
                        help='Priority level')
    parser.add_argument('--how-discovered', default='manually logged',
                        dest='how_discovered',
                        help='Context for how this was found')
    parser.add_argument('--target', default=None,
                        help='Target project (routes to that project\'s ticket DB). '
                             'Defaults to active project in projects.yaml.')

    args = parser.parse_args()

    result = create_ticket(
        ticket_type=args.ticket_type,
        title=args.title,
        description=args.description,
        project=args.project,
        how_discovered=args.how_discovered,
        priority=args.priority,
        target=args.target,
    )

    cli_finish(result, ok=f"{result.get('id')} created" if result.get('success') else "")


if __name__ == '__main__':
    main()
