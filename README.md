# simplex_mind

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

The **brain repo** — a project-agnostic AI agent toolkit that provides persistent memory, ticket tracking, conversation history, structured git commits, and a response summary protocol. It sits alongside your project repos as a sibling, not inside them.

## Architecture

```
~/projects/
├── simplex_mind/              ← brain repo (Claude launches here)
│   ├── CLAUDE.md              ← agnostic base instructions
│   ├── projects.yaml          ← maps project names → paths
│   ├── database/              ← all persistent data
│   │   ├── memory/            ← memory.db, MEMORY.md, systems.md, logs/
│   │   ├── tickets.db         ← ticket tracking
│   │   ├── conversation_history.db  ← conversation transcripts
│   │   └── ARCHITECTURE.md
│   └── src/utils/agent_skills/ ← all tools
│
├── my-project/               ← project workspace (branches freely)
│   ├── CLAUDE.md.ref          ← project-specific instructions
│   ├── src/, goals/, args/    ← project code
│   └── ...
│
└── (future projects)/
```

**Key insight:** Claude's operational state (instructions, memory, tickets, conversation history) lives in simplex_mind and is stable. Project code lives in its own repo and branches freely. Switching branches in a project repo never affects Claude's brain.

## Compatible AI Tools

| Tool | Instruction file |
|------|-----------------|
| Claude Code | `CLAUDE.md` |
| OpenAI Codex, Cursor, Windsurf, GitHub Copilot Workspace | `AGENTS.md` |

## What's included

- **Memory system** — SQLite-backed with daily logs, MEMORY.md sync, systems inventory, session digest, and optional semantic search
- **Ticket tracker** — JIRA-like issue tracking (configurable PREFIX-NNN IDs) with CLI tools
- **Conversation history** — Verbatim transcript storage from Claude Code JSONL files; cron-ingested; FTS5 search
- **Git wrapper** — Structured git operations scoped to framework files
- **Session digest** — Focused context loader (< 200 lines): open tickets, decisions, systems, git
- **Project registry** — `projects.yaml` maps project names to paths; Claude loads the active project's `CLAUDE.md.ref`

## Installation

1. Clone this repo alongside your project:
```bash
cd ~/projects
git clone <repo-url> simplex_mind
```

2. Create and activate the virtual environment:
```bash
cd ~/projects/simplex_mind
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Optional — enables semantic memory search:
# pip install openai numpy rank_bm25
```

3. Run the initializer:
```bash
python3 src/utils/agent_skills/init.py --prefix MY
```

4. Set up conversation history auto-ingestion (cron):
```bash
crontab -e
# Add:
*/5 * * * * ~/projects/simplex_mind/venv/bin/python ~/projects/simplex_mind/src/utils/agent_skills/conversation/conversation_ingest.py >> ~/projects/simplex_mind/logs/conversation_ingest.log 2>&1
```

5. Register your project in `projects.yaml`:
```yaml
projects:
  my-project:
    path: ~/projects/my-project
    ref_file: CLAUDE.md.ref
    active: true
```

6. Create the initial git commit:
```bash
python3 src/utils/agent_skills/git_commit.py init
```

## Adding a Project

1. Add an entry to `projects.yaml` with `path`, `ref_file`, and `active: false`
2. Create `CLAUDE.md.ref` in the project root with project-specific instructions
3. Set the new project to `active: true` (and the old one to `false`)
4. Start a new session — Claude will load the new project's instructions

## Configuration

`init.py` creates `database/config.json` on first run.

| Field | Type | Description |
|-------|------|-------------|
| `ticket_prefix` | string | Prefix for ticket IDs (e.g. `CORN` → `CORN-001`) |
| `project_name` | string | Human-readable project name |
| `project_description` | string | Short description |
| `tech_stack` | string | Comma-separated tech stack |
| `onboarding_complete` | boolean | Set to `true` after initial onboarding |

## Prerequisites

- Python 3.10+
- Git
- `pip install -r requirements.txt` (required)
- `pip install openai numpy rank_bm25` (optional — semantic search)

## Directory Structure

```
src/utils/agent_skills/
├── __init__.py
├── manifest.md              # Tool inventory
├── init.py                  # Project bootstrapper
├── git_commit.py            # Git wrapper
├── track_tokens.py          # Token tracking (optional)
├── memory/
│   ├── memory_db.py         # SQLite CRUD
│   ├── memory_write.py      # Write to logs + DB
│   ├── memory_read.py       # Load memory at session start
│   ├── memory_sync.py       # Regenerate MEMORY.md from DB
│   ├── session_digest.py    # Session-start context digest
│   ├── hybrid_search.py     # BM25 + vector search
│   ├── semantic_search.py   # Vector similarity search
│   ├── embed_memory.py      # OpenAI embeddings
│   └── memory_post_run.py   # Post-run metrics writer
├── tickets/
│   ├── ticket_db.py         # SQLite CRUD
│   ├── ticket_create.py     # CLI: create ticket
│   ├── ticket_list.py       # CLI: list tickets
│   ├── ticket_read.py       # CLI: read ticket
│   └── ticket_update.py     # CLI: update ticket
└── conversation/
    ├── conversation_db.py    # SQLite + FTS5 CRUD
    ├── conversation_ingest.py # JSONL parser (multi-source)
    └── conversation_read.py  # CLI: search, list, read
```

## Usage

All scripts run from the simplex_mind root via `python3 src/utils/agent_skills/...`.

### Session Start
```bash
python3 src/utils/agent_skills/memory/session_digest.py
```

### Memory
```bash
python3 src/utils/agent_skills/memory/memory_write.py --content "..." --type fact --importance 7
python3 src/utils/agent_skills/memory/memory_read.py --format markdown
python3 src/utils/agent_skills/memory/hybrid_search.py --query "..."
python3 src/utils/agent_skills/memory/memory_sync.py
```

### Tickets
```bash
python3 src/utils/agent_skills/tickets/ticket_create.py --type bug --title "..." --priority high
python3 src/utils/agent_skills/tickets/ticket_list.py --status open
python3 src/utils/agent_skills/tickets/ticket_read.py --id CORN-001
python3 src/utils/agent_skills/tickets/ticket_update.py --id CORN-001 --status done
```

### Conversation History
```bash
python3 src/utils/agent_skills/conversation/conversation_ingest.py
python3 src/utils/agent_skills/conversation/conversation_read.py --action search --query "..."
python3 src/utils/agent_skills/conversation/conversation_read.py --action list-sessions
python3 src/utils/agent_skills/conversation/conversation_read.py --action stats
```

### Git
```bash
python3 src/utils/agent_skills/git_commit.py init
python3 src/utils/agent_skills/git_commit.py commit -m "message"
python3 src/utils/agent_skills/git_commit.py status
```
