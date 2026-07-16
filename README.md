# simplex_mind

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

The **brain repo** — a project-agnostic AI agent toolkit that provides persistent memory, ticket tracking, conversation history, structured git commits, and a response summary protocol. It sits alongside your project repos as a sibling, not inside them.

## Architecture

```
~/projects/
├── simplex_mind/              ← brain repo (your AI agent launches here)
│   ├── CLAUDE.md              ← instructions for Claude Code
│   ├── AGENTS.md              ← instructions for Codex / Cursor / Windsurf
│   ├── projects.yaml          ← maps project names → paths
│   ├── subconscious/          ← reasoning-philosophy piece library (canonical)
│   ├── database/              ← all persistent data
│   │   ├── memory/            ← memory.db, MEMORY.md, systems.md, logs/,
│   │   │                            subconscious_index.json (derived, gitignored)
│   │   ├── tickets.db         ← simplex_mind's own (fallback) ticket DB
│   │   ├── conversation_history.db  ← conversation transcripts + token usage
│   │   └── ARCHITECTURE.md
│   └── src/utils/agent_skills/ ← all tools
│
├── my-project/               ← project workspace (branches freely)
│   ├── CLAUDE.md.ref          ← project-specific instructions
│   ├── database/tickets.db    ← this project's tickets (each project has its own)
│   ├── src/, goals/, args/    ← project code
│   └── ...
│
└── (future projects)/
```

**Key insight:** Your agent's operational state (instructions, memory, tickets, conversation history) lives in simplex_mind and is stable. Project code lives in its own repo and branches freely. Switching branches in a project repo never affects the agent's brain.

## Compatible AI Tools

| Tool | Instruction file |
|------|-----------------|
| Claude Code | `CLAUDE.md` |
| OpenAI Codex, Cursor, Windsurf, GitHub Copilot Workspace | `AGENTS.md` |

## What's included

- **Memory system** — SQLite-backed with daily logs, MEMORY.md sync, systems inventory, session digest, and local semantic search (fastembed)
- **Ticket tracker** — JIRA-like issue tracking (configurable PREFIX-<MACHINE>-NNN IDs) with CLI tools; per-project databases routed via `projects.yaml`
- **Subconscious** — Reasoning-philosophy pieces injected into context only when the prompt topically matches (keyword + embedding triggers via a UserPromptSubmit hook); library and generic default keywords ship in this repo's `subconscious/` dir, personal trigger phrasing layers on top locally (gitignored overlay), mined from each user's own conversations
- **Conversation history** — Verbatim transcript storage from AI assistant JSONL transcripts; cron-ingested; FTS5 search
- **Git wrapper** — Structured git operations scoped to framework files
- **Session digest** — Focused context loader (< 200 lines): open tickets, decisions, systems, git
- **Project registry** — `projects.yaml` maps project names to paths; the agent loads the active project's ref file

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
pip install -r requirements.txt   # includes fastembed — local semantic search works out of the box
# Optional — OpenAI embeddings fallback instead of the local model:
# pip install openai
```

3. Run the initializer:
```bash
python3 src/utils/agent_skills/init.py --prefix PROJ
```

4. Set up conversation history auto-ingestion (cron):
```bash
crontab -e
# Add:
*/5 * * * * ~/projects/simplex_mind/venv/bin/python ~/projects/simplex_mind/src/utils/agent_skills/conversation/conversation_ingest.py >> ~/projects/simplex_mind/logs/conversation_ingest.log 2>&1
```

5. Register your project in `projects.yaml`:
```yaml
machine: L1  # this machine's ticket-ID segment (e.g. L1 = laptop 1, D1 = desktop 1)
projects:
  my-project:
    path: ~/projects/my-project
    ref_file: CLAUDE.md.ref
    ticket_prefix: PROJ
    branch: my-project
```

6. Create the initial git commit:
```bash
python3 src/utils/agent_skills/git_commit.py init
```

## Adding a Project

1. Add an entry to `projects.yaml` with `path`, `ref_file`, `ticket_prefix`, and `branch`
2. Create `CLAUDE.md.ref` in the project root with project-specific instructions
3. Create the project's branch in simplex_mind from master: `git checkout master && git checkout -b <branch>`
4. `git checkout <branch>` to activate the project, then start a new session — your agent will load the new project's instructions

The active project is derived from the current simplex_mind git branch (matching against each project's `branch:` field). On `master`, no project is active.

## Configuration

`init.py` creates `database/config.json` on first run.

| Field | Type | Description |
|-------|------|-------------|
| `ticket_prefix` | string | Prefix for ticket IDs (e.g. `PROJ` → `PROJ-L1-001`) |
| `project_name` | string | Human-readable project name |
| `project_description` | string | Short description |
| `tech_stack` | string | Comma-separated tech stack |
| `onboarding_complete` | boolean | Set to `true` after initial onboarding |

## Prerequisites

- Python 3.10+
- Git
- `pip install -r requirements.txt` (required — includes fastembed for local semantic search)
- `pip install openai` (optional — OpenAI embeddings fallback)

## Directory Structure

```
src/utils/agent_skills/
├── __init__.py
├── manifest.md              # Tool inventory
├── init.py                  # Project bootstrapper
├── git_commit.py            # Git wrapper
├── project_resolver.py      # Branch → project resolution, ticket DB routing
├── track_tokens.py          # Token tracking (optional)
├── memory/
│   ├── memory_db.py         # SQLite CRUD
│   ├── memory_write.py      # Write to logs + DB
│   ├── memory_read.py       # Load memory at session start
│   ├── memory_sync.py       # Regenerate MEMORY.md from DB
│   ├── session_digest.py    # Session-start context digest
│   ├── hybrid_search.py     # BM25 + vector search
│   ├── semantic_search.py   # Vector similarity search
│   ├── embed_memory.py      # Embeddings (local fastembed; OpenAI fallback)
│   └── memory_post_run.py   # Post-run metrics writer
├── tickets/
│   ├── ticket_db.py         # SQLite CRUD (per-project routing)
│   ├── ticket_create.py     # CLI: create ticket
│   ├── ticket_list.py       # CLI: list tickets
│   ├── ticket_read.py       # CLI: read ticket
│   ├── ticket_update.py     # CLI: update ticket
│   └── ticket_migrate.py    # Historical: one-time shared→per-project migration
├── conversation/
│   ├── conversation_db.py    # SQLite + FTS5 CRUD
│   ├── conversation_ingest.py # JSONL parser (multi-source)
│   └── conversation_read.py  # CLI: search, list, read
└── subconscious/
    ├── subconscious_index.py  # embed library pieces → retrieval index
    ├── subconscious_recall.py # UserPromptSubmit hook: inject matching pieces
    └── subconscious_mine.py   # mine conversation history for triggers
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
python3 src/utils/agent_skills/tickets/ticket_read.py --id PROJ-L1-001
python3 src/utils/agent_skills/tickets/ticket_update.py --id PROJ-L1-001 --status done
```

### Subconscious
```bash
python3 src/utils/agent_skills/subconscious/subconscious_index.py          # rebuild after editing pieces
python3 src/utils/agent_skills/subconscious/subconscious_index.py --list   # inspect
python3 src/utils/agent_skills/subconscious/subconscious_mine.py           # mine history for new triggers
```
The recall hook (`subconscious_recall.py`) runs automatically per prompt via `.claude/settings.json` — no manual invocation. See the Subconscious section of `CLAUDE.md` / `AGENT_PROTOCOL.md` for how pieces and triggers work.

### Conversation History
```bash
python3 src/utils/agent_skills/conversation/conversation_ingest.py
python3 src/utils/agent_skills/conversation/conversation_read.py --action search --query "..."
python3 src/utils/agent_skills/conversation/conversation_read.py --action list-sessions
python3 src/utils/agent_skills/conversation/conversation_read.py --action stats
```

Ingestion also captures per-response API token usage into the `message_usage` table
(input/output/cache counts — including tool-call-only responses), so token accounting
survives Claude Code's ~30-day transcript cleanup. Lifetime totals + per-month breakdown
are included in `--action stats`.

### Git
```bash
python3 src/utils/agent_skills/git_commit.py init
python3 src/utils/agent_skills/git_commit.py commit -m "message"
python3 src/utils/agent_skills/git_commit.py status
```
