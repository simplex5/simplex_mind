# simplex_mind

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

A reusable Claude Code agent toolkit that gives any project persistent memory, JIRA-like ticket tracking, structured git commits, and a response summary protocol.

## What's included

- **Memory system** — SQLite-backed persistent memory with daily logs, MEMORY.md curation, and optional semantic search via OpenAI embeddings
- **Ticket tracker** — JIRA-like issue tracking (configurable PREFIX-NNN IDs via `database/config.json`) with CLI tools for create/read/update/list
- **Git wrapper** — Structured git operations scoped to framework files
- **Token tracker** — Optional metrics logging for multi-agent orchestration (requires external statusline.sh)
- **Agent protocol** — CLAUDE.md instructions for response summaries, guardrails, input prefixes, and branching workflow

## Installation

1. Copy the `src/` directory into your project root:

```bash
cp -r ~/projects/simplex_mind/src/ /path/to/your/project/src/
```

2. Run the initializer:

```bash
python src/utils/claude_code_skills/init.py
```

This creates `database/`, `logs/`, `.tmp/`, and seed files (idempotent — safe to re-run).

3. Set your ticket prefix. The onboarding flow handles this automatically, or pass it to init.py:
```bash
python src/utils/claude_code_skills/init.py --prefix CORN
```

4. Configure your `CLAUDE.md`. The onboarding flow (defined in `SETUP.md`) walks you through this on first session. Alternatively, paste the sections from `SETUP.md` manually.

5. Create the initial git commit:

```bash
python src/utils/claude_code_skills/git_commit.py init
```

## Configuration

`init.py` creates `database/config.json` on first run. All fields are optional except `ticket_prefix`.

| Field | Type | Description |
|-------|------|-------------|
| `ticket_prefix` | string | Prefix for ticket IDs (e.g. `MTX` → `MTX-001`) |
| `project_name` | string | Human-readable project name |
| `project_description` | string | Short description |
| `tech_stack` | string | Comma-separated tech stack |
| `onboarding_complete` | boolean | Set to `true` after initial onboarding |

Example:

```json
{
  "ticket_prefix": "MTX",
  "project_name": "my-project",
  "project_description": "A short description",
  "tech_stack": "Python, SQLite",
  "onboarding_complete": true
}
```

Pass fields at init time or edit the file directly after creation.

## Prerequisites

- Python 3.10+
- Git
- `pip install python-dotenv` (required)
- `pip install openai numpy rank_bm25` (optional — enables semantic memory search)

## Directory structure

```
src/utils/claude_code_skills/
├── __init__.py
├── manifest.md              # Tool inventory
├── init.py                  # Project bootstrapper
├── git_commit.py            # Git wrapper
├── track_tokens.py          # Token usage tracking (optional)
├── memory/
│   ├── __init__.py
│   ├── memory_db.py         # SQLite CRUD
│   ├── memory_write.py      # Write to logs + DB
│   ├── memory_read.py       # Load memory at session start
│   ├── hybrid_search.py     # BM25 + vector search
│   ├── semantic_search.py   # Vector similarity search
│   ├── embed_memory.py      # OpenAI embeddings
│   └── memory_post_run.py   # Post-run metrics writer
└── tickets/
    ├── __init__.py
    ├── ticket_db.py          # SQLite CRUD (prefix from config.json)
    ├── ticket_create.py      # CLI: create ticket
    ├── ticket_list.py        # CLI: list tickets
    ├── ticket_read.py        # CLI: read ticket
    └── ticket_update.py      # CLI: update ticket
```

## Notes

- DB path resolution uses `Path(__file__).parent` chains to find the project root. This works as long as `src/utils/claude_code_skills/` is preserved as a directory structure.
- `track_tokens.py` depends on an external `statusline.sh` script for the `--claude-delta` mode. This is optional and can be ignored if you don't need token tracking.
- The `memory_post_run.py` script is designed for orchestrator pipelines. It's optional for projects that don't use automated run loops.

## Usage

All scripts run from the project root via `python src/utils/claude_code_skills/...`.

### Memory

```bash
# Write a fact to daily log + SQLite
python src/utils/claude_code_skills/memory/memory_write.py \
    --content "User prefers semantic search" --type preference --importance 7

# Load memory at session start (MEMORY.md + last 2 days of logs)
python src/utils/claude_code_skills/memory/memory_read.py

# Search memory (keyword + optional vector)
python src/utils/claude_code_skills/memory/hybrid_search.py --query "semantic search"
```

### Tickets

```bash
# Create a bug ticket
python src/utils/claude_code_skills/tickets/ticket_create.py \
    --type bug --title "Canvas flickers on resize" --priority high

# List open tickets
python src/utils/claude_code_skills/tickets/ticket_list.py

# Read a ticket
python src/utils/claude_code_skills/tickets/ticket_read.py --id MTX-001

# Update a ticket
python src/utils/claude_code_skills/tickets/ticket_update.py \
    --id MTX-001 --status done --note "Fixed in commit abc123"
```

### Git

```bash
# Initialize repo and create first commit
python src/utils/claude_code_skills/git_commit.py init

# Commit all framework files
python src/utils/claude_code_skills/git_commit.py commit -m "Add feature X"

# Commit specific paths only
python src/utils/claude_code_skills/git_commit.py commit -m "Update README" \
    --paths README.md CLAUDE.md
```
