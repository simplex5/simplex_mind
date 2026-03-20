#!/usr/bin/env python3
"""
simplex_mind — Project Initializer
Run once after installing: python src/utils/agent_skills/init.py
Creates project-specific runtime directories — never overwrites existing files.
"""

import argparse
import json
import sqlite3
from pathlib import Path

# Allow importing memory_db from same package
sys_path_entry = str(Path(__file__).parent)
import sys
if sys_path_entry not in sys.path:
    sys.path.insert(0, sys_path_entry)

ROOT = Path(__file__).parent.parent.parent.parent


def write_if_missing(path: Path, content: str):
    if path.exists():
        print(f"  skip   {path.relative_to(ROOT)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"  create {path.relative_to(ROOT)}")


def touch_if_missing(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
        print(f"  create {path.relative_to(ROOT)}")
    else:
        print(f"  skip   {path.relative_to(ROOT)}")


def mkdir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def _write_config(args: argparse.Namespace) -> None:
    """Write provided CLI args to database/config.json, merging with existing."""
    config_path = ROOT / "database" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    existing = {}
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    if args.prefix:
        existing["ticket_prefix"] = args.prefix
    if args.project_name:
        existing["project_name"] = args.project_name
    if args.project_description:
        existing["project_description"] = args.project_description
    if args.tech_stack:
        existing["tech_stack"] = args.tech_stack

    # Only write if we have values to set
    if any(getattr(args, k) for k in ("prefix", "project_name", "project_description", "tech_stack")):
        config_path.write_text(json.dumps(existing, indent=2) + "\n")
        print(f"  write  database/config.json")


def main():
    parser = argparse.ArgumentParser(description="simplex_mind — project initializer")
    parser.add_argument("--prefix", help="Ticket ID prefix (e.g. CORN, FLUX, EGG)")
    parser.add_argument("--project-name", help="Project name")
    parser.add_argument("--project-description", help="One-line project description")
    parser.add_argument("--tech-stack", help="Comma-separated tech stack")
    args = parser.parse_args()

    print("simplex_mind — initializing project runtime...\n")

    # ── database/memory ───────────────────────────────────────────────────
    write_if_missing(ROOT / "database/memory/MEMORY.md", """\
# Persistent Memory

> This file contains curated long-term facts, preferences, and context that persist across sessions.
> The AI reads this at the start of each session. You can edit this file directly.

## Key Facts

## Learned Behaviors

- Always check src/utils/manifest.md before creating new scripts

## Git Integration

- Tool: src/utils/agent_skills/git_commit.py — subcommands: init, status, commit, diff

## Current Configuration

---

*Last updated: (date)*
*This file is the source of truth for persistent facts. Edit directly to update.*
""")

    mkdir(ROOT / "database/memory/logs")

    # ── logs ──────────────────────────────────────────────────────────────
    mkdir(ROOT / "logs")
    touch_if_missing(ROOT / "logs/.gitkeep")

    # ── scratch ───────────────────────────────────────────────────────────
    mkdir(ROOT / ".tmp")

    # ── databases ─────────────────────────────────────────────────────────
    _init_databases()

    # ── config.json ────────────────────────────────────────────────────────
    _write_config(args)

    print("\nRuntime initialized.\n")
    print("Next steps:")
    print("  1. python src/utils/agent_skills/git_commit.py init")
    print("  2. Configure your CLAUDE.md or AGENTS.md (see SETUP.md for the onboarding flow)")


def _init_databases():
    database_dir = ROOT / "database" / "memory"
    database_dir.mkdir(parents=True, exist_ok=True)

    mem_db = database_dir / "memory.db"
    if not mem_db.exists():
        from memory.memory_db import get_connection
        conn = get_connection()
        conn.close()
        print(f"  create database/memory/memory.db")
    else:
        print(f"  skip   database/memory/memory.db")

    # Per-project ticket DBs are created via project_resolver routing.
    # For simplex_mind's own brain ticket DB:
    tickets_db = ROOT / "database" / "tickets.db"
    tickets_db.parent.mkdir(parents=True, exist_ok=True)
    if not tickets_db.exists():
        from tickets.ticket_db import get_connection as get_ticket_conn
        conn = get_ticket_conn(db_path=tickets_db)
        conn.close()
        print(f"  create database/tickets.db")
    else:
        print(f"  skip   database/tickets.db")

    conv_db = ROOT / "database" / "conversation_history.db"
    if not conv_db.exists():
        from conversation.conversation_db import get_connection as get_conv_conn
        conn = get_conv_conn()
        conn.close()
        print(f"  create database/conversation_history.db")
    else:
        print(f"  skip   database/conversation_history.db")


if __name__ == "__main__":
    main()
