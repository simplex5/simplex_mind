# PRIVACY.md — What simplex_mind Stores, Where, and How to Remove It

simplex_mind is a local-first system: everything it collects lives in SQLite files under
`database/` in this repo, which is gitignored runtime state — **nothing is committed, synced,
or sent anywhere by default**. This file is the honest inventory.

## What is collected

| Data | Where | How |
|------|-------|-----|
| **Verbatim conversation transcripts** (your prompts + assistant responses) | `database/conversation_history.db` (`sessions`, `messages` + full-text index) | Ingested from Claude Code's own JSONL transcripts under `~/.claude/projects/` — by a Stop hook after every response and a 5-minute cron/Task Scheduler job |
| **Per-response token usage** (input/output/cache counts, model, timestamps) | `database/conversation_history.db` (`message_usage`) | Same ingestion; kept deliberately long-term so cost accounting survives Claude Code's ~30-day transcript cleanup |
| **Memories** (facts, decisions, preferences you or the agent record) | `database/memory/memory.db`, `database/memory/MEMORY.md`, daily logs | Written explicitly via `memory_write.py` / `simplex memory write` |
| **Memory embeddings** (vector representations of memory content) | `database/memory/memory.db` | Computed **locally** via fastembed by default. If an OpenAI API key is configured, `embed_memory.py` falls back to OpenAI — memory content is then sent to OpenAI. No key, no egress. |
| **Tickets** (work items, notes) | `database/tickets.db` per project | Written via ticket tools |
| **Project metadata** (name, description, tech stack, ticket prefix, onboarding state) | `database/config.json` (local, never committed) | Written during onboarding via `init.py` flags |
| **Subconscious keyword mining** | `database/memory/subconscious_*.json` | Reads your local transcripts to propose trigger keywords; runs locally |

## Where it does NOT go

- Not into git: `database/*` is gitignored (only `ARCHITECTURE.md`, `MEMORY.md`, `systems.md` are tracked).
- Not to any server: there is no telemetry, no sync, no remote storage in this system.
- The only potential egress is the **optional** OpenAI embedding fallback above, and it is off
  unless you configure a key.

## How to remove data

- **Transcripts:** `simplex history purge --older-than 90 --dry-run` to preview, then re-run
  with `--yes`. Selectors: `--project`, `--older-than <days>`, `--session <id>`, `--all`.
  Token-usage rows are preserved by default (cost accounting); add `--with-usage` to remove
  them too, and `--vacuum` to reclaim disk space.
- **Upstream copies:** Claude Code's own transcripts under `~/.claude/projects/` are the
  source the ingester reads. Purging the database does not touch them — delete those JSONL
  files separately if you want the content gone everywhere. (Claude Code also cleans them up
  itself after ~30 days.)
- **Memories:** find the entry with `simplex memory search --query "..."`, then deactivate it
  via `memory_db.py`'s soft-delete (`is_active = 0`), or delete `database/memory/memory.db`
  and the markdown logs outright.
- **Backups:** `simplex backup` writes copies under `database/backups/` — delete old backup
  directories along with anything you purge.
- **Everything:** deleting the `database/` directory removes all collected data on this
  machine; `init.py` recreates empty scaffolding.

## Multi-machine note

Each machine keeps its own `database/` — there is no cross-machine sync, so removal is
per-machine (this is also why `config.json` is local: see SETUP.md's fresh-clone vs
lost-config detection). If you gave someone a clone of this repo, they received **no
data**: a fresh clone contains empty scaffolding only.
