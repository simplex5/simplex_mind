# simplex_mind

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

The **brain repo** — a project-agnostic AI agent toolkit that provides persistent memory, ticket tracking, conversation history, structured git commits, and a response summary protocol. It sits alongside your project repos as a sibling, not inside them.

> **New here?** [HUMAN_INSTRUCTIONS.md](HUMAN_INSTRUCTIONS.md) is the step-by-step quick start — clone, venv, onboarding, and how to verify it worked.

> **On native Windows?** See [SETUP-WINDOWS.md](SETUP-WINDOWS.md) — use `py` instead of `python3`, and `scripts/setup_windows_tasks.ps1` instead of the cron lines below.

> **What does it store about me?** [PRIVACY.md](PRIVACY.md) — the honest inventory: transcripts, token usage, memories; all local SQLite, and how to remove any of it.

## Architecture

```
~/projects/
├── simplex_mind/              ← brain repo (your AI agent launches here)
│   ├── CLAUDE.md              ← instructions for Claude Code
│   ├── AGENTS.md              ← instructions for Codex / Cursor / Windsurf
│   ├── PRIVACY.md             ← what is stored, where, how to remove it
│   ├── projects.yaml          ← maps project names → paths
│   ├── subconscious/          ← reasoning-philosophy piece library (canonical)
│   ├── .github/workflows/     ← CI (pytest + ruff, ubuntu + windows)
│   ├── database/              ← all persistent data
│   │   ├── memory/            ← memory.db, MEMORY.md, systems.md, logs/,
│   │   │                            subconscious_index.json (derived, gitignored)
│   │   ├── config.json        ← local onboarding/config state (never committed)
│   │   ├── tickets.db         ← simplex_mind's own (fallback) ticket DB
│   │   ├── conversation_history.db  ← conversation transcripts + token usage
│   │   ├── hooks.db           ← hook session state + event log (runtime, gitignored)
│   │   ├── backups/           ← `simplex backup` snapshots (gitignored)
│   │   └── ARCHITECTURE.md
│   ├── src/utils/agent_skills/ ← the tools (script paths, always work)
│   └── src/simplex_cli/       ← installable `simplex` CLI (pip install -e .)
│
├── my-project/               ← project workspace (branches freely)
│   ├── CLAUDE.md.ref          ← project-specific instructions
│   ├── database/tickets.db    ← this project's tickets (each project has its own)
│   ├── src/                   ← project code
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
- **Session digest** — Focused context loader (< 200 lines): open tickets, decisions, systems, git; broken subsystems render as `UNAVAILABLE`, never as healthy emptiness
- **Project registry** — `projects.yaml` maps project names to paths; the agent loads the active project's ref file
- **`simplex` CLI** — one installed command fronting the daily-driver tools (`pip install -e .`): `simplex doctor`, `simplex ticket list`, `simplex memory search`, `simplex project use <name>`, …
- **Doctor** — a full battery of read-only health checks with per-check remediation (`simplex doctor`, exit 1 when degraded); classifies fresh-clone vs lost-config onboarding states
- **Protocol hooks** — beyond subconscious recall: a SessionStart digest, a UserPromptSubmit protocol gate (memory-cadence demands), and a PreToolUse ticket-gate that warns once per session (`[ticket-gate: ...]` marker) when a file edit starts with no open ticket
- **Backup & retention** — `simplex backup` (consistent SQLite snapshots) and `simplex history purge` (transcript deletion by project/age; see [PRIVACY.md](PRIVACY.md))

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
pip install -e .                  # installs the `simplex` CLI into the venv
# Optional — OpenAI embeddings fallback instead of the local model:
# pip install openai
```

3. Run the initializer:
```bash
python3 src/utils/agent_skills/init.py --prefix PROJ
```
Do **not** pass `--mark-onboarded` here — a fresh clone without that marker is exactly
what routes your agent into the SETUP.md onboarding flow, which sets it at the end.
(The flag still exists for the lost-config recovery path — see SETUP.md.)

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

7. Verify everything is wired up:
```bash
python3 src/utils/agent_skills/doctor.py   # or: simplex doctor — exit 0 = HEALTHY
```

## Adding a Project

1. Add an entry to `projects.yaml` with `path`, `ref_file`, `ticket_prefix`, and `branch`
2. Create `CLAUDE.md.ref` in the project root with project-specific instructions
3. Create the project's branch in simplex_mind from master: `git checkout master && git checkout -b <branch>`
4. `git checkout <branch>` to activate the project, then start a new session — your agent will load the new project's instructions

The active project is derived from the current simplex_mind git branch (matching against each project's `branch:` field). On `master`, no project is active.

**Ref files are agent-agnostic.** `ref_file` is a single key, so that one file is read by every
agent — Claude Code, Codex, Cursor, Windsurf. The `CLAUDE.md.ref` name is conventional, not
functional, and there is no per-agent variant. Keep project **facts** in it (paths, git rules,
tech stack, meta-file handling, testing conventions) and fence anything agent-specific under a
heading that names the agent, e.g. `## Claude Code only — subagent delegation`, so other agents
skip it instead of attempting instructions for tools they don't have.

## Configuration

`database/config.json` is **local runtime state** — written during onboarding (`init.py`
flags, final step `init.py --mark-onboarded`), never committed. A fresh clone has no
config.json, which is exactly what routes agents into the SETUP.md onboarding flow.
Verify any checkout with `python3 src/utils/agent_skills/doctor.py`.

See [PRIVACY.md](PRIVACY.md) for exactly what this system stores (transcripts, token
usage, memories), where it lives, and how to remove it.

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
- `pip install -e .` (required for the `simplex` CLI; editable install only)
- `pip install openai` (optional — OpenAI embeddings fallback)

## Directory Structure

```
src/simplex_cli/             # installable `simplex` CLI (pip install -e .)
├── cli.py                   # thin dispatcher over the agent-skills tools
└── __main__.py              # `py -m simplex_cli` fallback

src/utils/agent_skills/
├── __init__.py
├── manifest.md              # Tool inventory
├── _common.py               # Shared paths (REPO_ROOT), CLI epilogue, migrations helper
├── init.py                  # Project bootstrapper (--mark-onboarded writes config.json)
├── doctor.py                # health checks; fresh-clone vs lost-config classification
├── backup_db.py             # SQLite online-backup of persistent DBs → database/backups/
├── git_commit.py            # Git wrapper
├── project_resolver.py      # Branch → project resolution, ticket DB routing
├── track_tokens.py          # Token tracking (optional)
├── memory/
│   ├── memory_db.py         # SQLite CRUD
│   ├── memory_write.py      # Write to logs + DB (auto project:<name> tag)
│   ├── memory_read.py       # Load memory at session start
│   ├── memory_sync.py       # Regenerate MEMORY.md from DB
│   ├── session_digest.py    # Session-start context digest (UNAVAILABLE on failure)
│   ├── protocol_gate.py     # UserPromptSubmit hook: cadence/autotune/routing demands
│   ├── hook_state.py        # hooks.db: durable hook session state + event log
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
│   ├── pretooluse_gate.py   # PreToolUse hook: warn-once ticket-before-edit gate
│   ├── ticket_renumber.py   # CLI: renumber ticket IDs
│   └── ticket_migrate.py    # Historical: one-time shared→per-project migration
├── conversation/
│   ├── conversation_db.py    # SQLite + FTS5 CRUD
│   ├── conversation_ingest.py # JSONL parser (multi-source)
│   ├── conversation_read.py  # CLI: search, list, read
│   └── conversation_purge.py # CLI: delete transcripts (see PRIVACY.md)
└── subconscious/
    ├── subconscious_index.py  # embed library pieces → retrieval index
    ├── subconscious_recall.py # UserPromptSubmit hook: inject matching pieces
    ├── subconscious_mine.py   # mine conversation history for triggers
    └── subconscious_autotune.py # weekly cron: queue gated keyword candidates
```

## Usage

All scripts run from the simplex_mind root via `python3 src/utils/agent_skills/...`.
With the venv active, every ticket, memory, history, and health/backup command below
also has a `simplex` equivalent (`simplex ticket list`, `simplex memory search`,
`simplex history stats`, …) — run `simplex --help` for the full list. The git,
subconscious, and maintenance scripts are script-path only. Script paths stay
canonical; the CLI is a convenience.

### Health & maintenance
```bash
simplex doctor          # read-only health checks with remediation lines; exit 1 when degraded
simplex status          # compact read-only status page
simplex backup          # consistent snapshots of all persistent DBs → database/backups/<UTC>/
                        # (hooks.db excluded — regenerable runtime state, self-prunes at 90 days)
simplex history purge --older-than 90 --dry-run   # transcript retention (PRIVACY.md)
```

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
python3 src/utils/agent_skills/tickets/ticket_list.py --query "campfire"  # duplicate check: LIKE over title+description, all statuses, no cap
python3 src/utils/agent_skills/tickets/ticket_read.py --id PROJ-L1-001
python3 src/utils/agent_skills/tickets/ticket_update.py --id PROJ-L1-001 --status done
```

### Subconscious
```bash
python3 src/utils/agent_skills/subconscious/subconscious_index.py          # rebuild after editing pieces
python3 src/utils/agent_skills/subconscious/subconscious_index.py --list   # inspect
python3 src/utils/agent_skills/subconscious/subconscious_mine.py           # mine history for new triggers
```
The recall hook (`subconscious_recall.py`) runs automatically per prompt via `.claude/settings.json` — no manual invocation, as do the other registered hooks: the SessionStart digest, the protocol gate, the PreToolUse ticket-gate (`tickets/pretooluse_gate.py`, warns once per session when a file edit starts with no open ticket), and the Stop-hook transcript ingest. See the Subconscious section of `CLAUDE.md` / `AGENT_PROTOCOL.md` for how pieces and triggers work.

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

Transcripts are stored verbatim — [PRIVACY.md](PRIVACY.md) documents exactly what is
collected and `conversation_purge.py` / `simplex history purge` deletes it by
project, age, or session (token usage preserved by default).

### Git
```bash
python3 src/utils/agent_skills/git_commit.py init
python3 src/utils/agent_skills/git_commit.py commit -m "message"
python3 src/utils/agent_skills/git_commit.py status
```

## Development

```bash
pip install -r requirements-dev.txt   # pytest + ruff
pytest                                # test suite (hermetic — never touches your real DBs)
ruff check .                          # lint
```

CI (`.github/workflows/ci.yml`) runs both on ubuntu-latest and windows-latest
(Python 3.10 and 3.12) for every push/PR to `develop` and `master`, then runs
`simplex doctor` on the bare checkout and asserts it exits nonzero reporting a
fresh clone — the onboarding-detection path is exercised on every push.
