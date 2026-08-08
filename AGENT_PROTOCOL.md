# Agent Protocol — Ticketing, Memory, Conversation History & Git

The simplex_mind brain repo provides persistent memory, issue tracking, conversation history,
and structured git commit behaviour across all projects.

---

## 1. Prerequisites

- Python 3.10+
- Git repository initialised
- simplex_mind cloned as a sibling repo (e.g. `~/projects/simplex_mind/`)
- Tools live in `src/utils/agent_skills/` (memory, tickets, conversation, subconscious,
  doctor, backup, git); the installable `simplex` CLI lives in `src/simplex_cli/`

---

## 2. Install dependencies

```bash
pip install -r requirements.txt
# Includes fastembed — semantic memory search runs fully locally, no API key.
pip install -e .
# Installs the `simplex` CLI into the venv — a unified front for every tool below:
# simplex doctor / status / digest / init / backup
# simplex ticket create|list|read|update
# simplex memory write|search|read|sync
# simplex history ingest|search|stats|purge
# simplex project use <name> (= git checkout of the project's branch) / project list
# The script paths in this document remain canonical and always work without the
# install — hooks and cron call them directly.
# Optional — OpenAI embeddings fallback instead of the local model:
# pip install openai
```

---

## 3. One-time init

```bash
python src/utils/agent_skills/init.py
```

Creates:
- `database/memory/MEMORY.md` — curated persistent memory file
- `database/memory/logs/` — daily log directory
- `database/memory/memory.db` — SQLite: facts, insights, daily logs
- `database/tickets.db` — SQLite: simplex_mind's own (fallback) issue tracker
- `database/conversation_history.db` — SQLite: conversation transcripts + token usage
- `database/config.json` — local onboarding/config state (**never committed**; written
  when init flags are passed)
- `logs/` and `.tmp/` — runtime directories

After setup is complete, mark onboarding done (the session-start check depends on it):
```bash
python src/utils/agent_skills/init.py --mark-onboarded
```
A missing/unmarked config.json routes agents into onboarding — deliberately, that is how
fresh clones are detected. Two states look similar but differ: **fresh clone** (no
projects.yaml, no databases → run full onboarding per SETUP.md) vs **lost config**
(databases exist but config.json is gone, e.g. after pulling the untracking migration →
just re-run `--mark-onboarded`, never re-onboard). `doctor.py` classifies this automatically.

Ticket IDs are machine-scoped: `PREFIX-<MACHINE>-NNN` (e.g. `SIMP-L1-042`), where MACHINE comes from the top-level `machine:` key in projects.yaml — each machine mints in its own namespace so IDs never collide across computers.

Per-project ticket databases (`<project_path>/database/tickets.db`) are created automatically
on first use, routed via `projects.yaml`.

Then create the first commit:
```bash
python src/utils/agent_skills/git_commit.py init
```

---

## 4. Protocol — Rules Claude or Codex must follow

### 4.1 Ticket Protocol

**Hard rule: Create a ticket before starting any work that edits files.**
No exceptions. Pure questions (using the `question:` prefix) are the only exemption.

**Routing:** Each registered project has its own ticket database at
`<project_path>/database/tickets.db`. Commands auto-target the active project (derived from
the current simplex_mind git branch); use `--target <name>` to override. Ticket ID prefix is
auto-inferred for read/update operations (e.g. PROJ-L1-122 → my-project). On `master` or `develop`
(no active project), tickets fall through to simplex_mind's own `database/tickets.db` under prefix `SIMP`.

**Commands:**
```bash
# Create (targets active project by default)
python src/utils/agent_skills/tickets/ticket_create.py \
    --type <bug|feature|task|improvement|documentation> \
    --title "Short summary" \
    --project <name> \
    --priority <low|medium|high|critical> \
    --description "Full details"
# Create targeting a specific project
python src/utils/agent_skills/tickets/ticket_create.py \
    --type task --title "..." --target other-project

# Read / list
python src/utils/agent_skills/tickets/ticket_read.py --id PROJ-L1-001
python src/utils/agent_skills/tickets/ticket_list.py --status open
python src/utils/agent_skills/tickets/ticket_list.py --all
python src/utils/agent_skills/tickets/ticket_list.py --target other-project
python src/utils/agent_skills/tickets/ticket_list.py --all-projects
python src/utils/agent_skills/tickets/ticket_list.py --query "campfire"  # duplicate check: LIKE over title+description, all statuses, no cap
python src/utils/agent_skills/tickets/ticket_list.py --all --limit 0     # full plain listing (default limit 50 prints a truncation banner)
```
List output is table-only; add `--json` for the machine-readable block.
```bash
# Update (auto-infers project from ticket ID prefix)
python src/utils/agent_skills/tickets/ticket_update.py \
    --id PROJ-L1-001 --status <open|in_progress|blocked|done|wont_fix>
python src/utils/agent_skills/tickets/ticket_update.py \
    --id PROJ-L1-001 --priority high --note "Context note"
```

**Also create a ticket immediately (without being asked) for:**
1. Bug discovered mid-task — log it even if it's not the current focus.
2. Feature or improvement mentioned in passing.
3. Topic shifted before resolution — log what was left unresolved.
4. Deferred work — user says "let's do X first" while discussing Y.
5. Anything unexpected — odd behaviour, suspicious code, missing file.
6. Memory writes — any time MEMORY.md or the DB is updated as part of a task.
7. Task incomplete — work stopped before finishing.

**Session triggers:**
- **Start**: run `ticket_list.py --status open`, report count + any critical/high items.
- **During work**: create tickets as issues surface — do not batch at the end.
- **End**: summarise tickets created this session by ID and title.

---

### 4.2 Memory Protocol

**Load at session start:**
```bash
python src/utils/agent_skills/memory/memory_read.py --format markdown
```

**Write a memory entry:**
```bash
python src/utils/agent_skills/memory/memory_write.py \
    --content "..." \
    --type <fact|preference|event|insight|task|relationship|decision|note> \
    --importance <1-10>
```

**Search memory:**
```bash
python src/utils/agent_skills/memory/hybrid_search.py --query "..."
```

When a project is active, `memory_write.py` auto-appends a `project:<name>` tag to the
database row (not the daily log). The `protocol_gate.py` UserPromptSubmit hook uses these
tags to scope its 5-resolved-tickets memory-cadence demand per project — a memory write
about another project no longer suppresses the active project's cadence.

**Direct MEMORY.md edits** (for curated, human-readable notes):
- Use Read + Edit tools on `database/memory/MEMORY.md`.
- Keep it under ~200 lines; content beyond that is truncated from context.
- Organise by topic, not chronologically. Remove outdated entries promptly.
- Save stable, confirmed patterns — not session-specific state.

---

### 4.3 Git Commit Rules

**Commands:**
```bash
python src/utils/agent_skills/git_commit.py status   # see what's changed
python src/utils/agent_skills/git_commit.py diff     # review before committing
python src/utils/agent_skills/git_commit.py commit -m "message"
python src/utils/agent_skills/git_commit.py commit -m "message" --paths path/to/file.py
```

By default `commit` stages all framework source directories and root config files.
Use `--paths` to stage specific files only.

**Commit automatically after:**
- Running `init.py` for the first time → use `git_commit.py init`
- Writing or updating any source file
- Modifying documentation, config, or instruction files at the project root

**Never commit after:**
- Benchmark or test runs — generated output is gitignored by design
- Edits to `database/memory/logs/` or `database/*.db` — local session state only

---

### 4.4 Response Summary Block

Append this block after **every** response that makes changes:

```
---
**Git:** committed `<message>` / no commit — <reason>
**Ticket:** created <ID> / updated <ID> / no ticket — <reason>
**DB:** wrote memory / updated ticket db / no db write — <reason>
**Notes:** <warnings, deferred items, anything actionable — omit if nothing>
**Commands:** `feature:` `bug:` `task:` `improvement:` `docs:` `question:`
```

Valid "no commit" reasons: read-only task, no source changes, benchmark run.
Valid "no ticket" reasons: pure conversation, already tracked, trivial one-liner.
Valid "no db write" reasons: read-only task, pure conversation.
`Commands` is always included and never omitted — it serves as a persistent cheatsheet for input prefix shortcuts.

---

---

## 4b. Subconscious — Context-Triggered Reasoning Philosophy

A library of reasoning-craft "pieces" is injected into context automatically when the
user's prompt matches — philosophy costs context only when relevant.

- **Library:** this repo's own `subconscious/` directory — committed, canonical,
  no configuration needed. Works across all projects and machines out of the box.
- **Engine:** a `UserPromptSubmit` hook runs `src/utils/agent_skills/subconscious/subconscious_recall.py`,
  which matches the prompt against `database/memory/subconscious_index.json`
  (keywords primary, embedding-cosine >= 0.70 as rescue), injects at most 2 pieces,
  each at most once per session, and always fails open.
- **Piece format:** frontmatter (`name`, `summary`, `keywords`, `source`) + prose body.
- **Keywords are two layers:** frontmatter `keywords:` = committed generic defaults (works
  out of the box); personal phrasing lives in the local, gitignored overlay
  `database/memory/subconscious_keywords.json` (`{"<piece-name>": ["phrase", ...]}`),
  merged at index build; tune via the miner. Never commit personal phrasing.
- **Rebuild after editing pieces or the keyword overlay:** `python3 src/utils/agent_skills/subconscious/subconscious_index.py`

**Growth loop:** when a session produces a durable reasoning lesson — a failure worth
preventing or an approach worth repeating — write it as a new piece in the library
and re-run the indexer. The library is meant to accumulate.

Periodically run `src/utils/agent_skills/subconscious/subconscious_mine.py` against conversation history to
surface new trigger phrasings and candidate groups from real usage.

**Autotune (weekly cron):** `src/utils/agent_skills/subconscious/subconscious_autotune.py` mines and queues gated
keyword candidates — nothing is applied without user approval. When the session digest shows
`PENDING KEYWORD CANDIDATES`, run `--review` and propose them to the user, then resolve with
`--approve`/`--reject piece:"phrase"`.

## 5. Input Prefixes

Prefix messages to lock in the ticket type and skip inference:

| Prefix | Ticket type | Use when… |
|--------|-------------|-----------|
| `feature:` | feature | Adding new capability |
| `bug:` | bug | Something is broken |
| `task:` | task | Work that doesn't fit above |
| `improvement:` | improvement | Enhancing something that works |
| `docs:` | documentation | Updating docs, CLAUDE.md or AGENTS.md, manifests |
| `question:` | — (none) | Just asking — no work tracked |

When a prefix is present: ticket is created at the start, prefix stripped before processing.
`question:` suppresses ticket creation entirely.

---

## 6. Schema Reference

**Ticket fields:** `id` (`PREFIX-<MACHINE>-NNN`), `ticket_type` (CLI flag: `--type`), `status`, `priority`, `title`, `description`, `project`, `how_discovered`, `notes`, `created_at`, `updated_at`, `resolved_at`

**Ticket types:** `bug` · `feature` · `task` · `improvement` · `documentation`

**Ticket statuses:** `open` · `in_progress` · `blocked` · `done` · `wont_fix`

**Ticket priorities:** `low` · `medium` · `high` · `critical`

**Memory types:** `fact` · `preference` · `event` · `insight` · `task` · `relationship` · `decision` (`note` is accepted by memory_write.py but is daily-log-only — never persisted to memory.db)

**Memory importance:** 1–10 (default 5). Higher = surfaced more prominently in search.

---

### 4.5 Conversation History Protocol

Conversation transcripts are ingested automatically from Claude Code JSONL files via two
mechanisms: a Stop hook in `.claude/settings.json` (runs after every Claude Code response,
~0 lag) and an optional cron job every 5 minutes (safety net for crashes or non-Claude agents).

**Search past conversations:**
```bash
python3 src/utils/agent_skills/conversation/conversation_read.py \
    --action search --query "..."
```

**List recent sessions:**
```bash
python3 src/utils/agent_skills/conversation/conversation_read.py \
    --action list-sessions --limit 10
```

**View full transcript:**
```bash
python3 src/utils/agent_skills/conversation/conversation_read.py \
    --action get-session --session-id <UUID>
```

**Manual ingest (if cron is not set up):**
```bash
python3 src/utils/agent_skills/conversation/conversation_ingest.py
```

Ingestion also captures per-response API token usage into the `message_usage` table
(input/output/cache counts — including tool-call-only responses), so token accounting
survives Claude Code's ~30-day transcript cleanup. Lifetime totals + per-month breakdown:
`conversation_read.py --action stats`.

**Delete stored transcripts** (retention/removal — see [PRIVACY.md](PRIVACY.md)):
```bash
python3 src/utils/agent_skills/conversation/conversation_purge.py \
    --older-than 90 --dry-run          # preview; selectors: --project/--older-than/--session/--all
# re-run with --yes to delete. Token usage (message_usage) is preserved by default;
# add --with-usage to remove it too. No stdin prompts — --yes is the confirmation.
```

---

### 4.6 Session Digest

Run at the start of every session for focused context (< 200 lines):

```bash
python3 src/utils/agent_skills/memory/session_digest.py
```

Outputs: open ticket count + critical/high items, recent decisions, active systems summary,
last 5 git commits. Broken subsystems render as `UNAVAILABLE — <reason> (run doctor.py)` —
never as a healthy-looking zero. The digest also self-heals onboarding state: it prints
`CONFIG LOST: …` (config.json missing but databases exist → run `init.py --mark-onboarded`)
or `ONBOARDING INCOMPLETE: …` (fresh clone → follow SETUP.md) under `## Environment`.

---

### 4.7 Decision Logging

When a significant architectural or process decision is made, log it:

```bash
python3 src/utils/agent_skills/memory/memory_write.py \
    --content "Decided to use FTS5 for conversation search" \
    --type decision --importance 7 --ticket PROJ-L1-087
```

Decisions appear in the session digest and in MEMORY.md (via memory_sync.py).

---

### 4.8 Memory Sync

Regenerate MEMORY.md from the database:

```bash
python3 src/utils/agent_skills/memory/memory_sync.py          # regenerate
python3 src/utils/agent_skills/memory/memory_sync.py --dry-run # preview
```

Non-destructive: only a marker-delimited AUTO-SYNC block is rebuilt from memory.db — all
hand-curated content outside the block is preserved verbatim.

---

### 4.9 Systems Inventory

Maintain `database/memory/systems.md` — a registry of significant features and systems.
Update when creating, removing, or significantly changing a system.
Read by session_digest.py for the "Active Systems" summary.

---

### 4.10 Doctor — Health Validation

```bash
python3 src/utils/agent_skills/doctor.py            # full validation, exit 1 when degraded
python3 src/utils/agent_skills/doctor.py --status   # compact status page, always exit 0
python3 src/utils/agent_skills/doctor.py --json     # machine-readable results
```

Thirteen read-only checks, each reporting `[ OK ]/[WARN]/[FAIL]` plus a one-line remediation:
onboarding classification, projects.yaml validity, every ticket DB, memory.db,
conversation DB + FTS, subconscious index freshness, autotune state, venv deps vs pins,
hook registration, hook events (degraded-outcome scan of hooks.db), db integrity
(FK + integrity_check over all local DBs incl. hooks.db), git identity,
branch→project mapping. `classify_onboarding()` (the
fresh-clone vs lost-config distinction from §3) is exported for reuse — session_digest.py
imports it. Run doctor after any pull that changes brain state, and whenever a digest
line or a `[protocol-gate degraded: …]` marker tells you to.

---

### 4.11 Backup

```bash
python3 src/utils/agent_skills/backup_db.py         # or: simplex backup
```

Copies memory.db, every ticket DB (brain + per-project), and conversation_history.db to
`database/backups/<YYYYMMDD-HHMMSSZ>/` using SQLite's online backup API — consistent even
while hooks hold the DBs open. Gitignored; no scheduling. Take one before any purge —
purge is irreversible without it.
