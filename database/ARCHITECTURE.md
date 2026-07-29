# Database Architecture

Five SQLite databases power simplex_mind's persistence layer: `memory.db`, `activity.db`,
`tickets.db` (one per project + a brain fallback), `conversation_history.db`, and
`hooks.db` (hook-layer session state + event log, SIMP-D2-038 — managed by
`memory/hook_state.py`: `hook_session_state` replaces the old per-session temp-JSON
throttle files, `hook_events` is an append-only observability log pruned past 90 days;
every access is fail-open so a broken hooks.db can never block a prompt).
Non-DB state also lives under `database/`: `config.json` (§7, local onboarding state),
the subconscious index + autotune state (§5), and `backups/` snapshots (§6) — all local,
none committed.

**Schema versioning (SIMP-L1-031):** every DB module declares an ordered `MIGRATIONS`
list applied by `_common.run_migrations()`, gated by SQLite's `PRAGMA user_version`.
Migration 1 is always the idempotent base schema, so pre-versioning databases replay it
as a no-op and then advance. To evolve a schema: append `(N+1, migration_fn)` to the
module's `MIGRATIONS` — never edit an existing migration that has shipped.

---

## 1. `database/memory/memory.db`

Managed by `src/utils/agent_skills/memory/memory_db.py`.

### Tables

| Table | Purpose |
|-------|---------|
| `memory_entries` | Long-term facts, insights, preferences, events, tasks, relationships |
| `daily_logs` | Per-day summaries and raw logs (date-keyed) |
| `memory_access_log` | Analytics trail — which entries were read/searched/updated |

### `memory_entries` columns

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `type` | TEXT | `fact`, `preference`, `event`, `insight`, `task`, `relationship`, `decision`, `note` |
| `content` | TEXT | Free-text entry |
| `content_hash` | TEXT UNIQUE | Dedup key (SHA of content) |
| `source` | TEXT | `user`, `inferred`, `session`, `external`, `system` |
| `confidence` | REAL | 0.0–1.0 (default 1.0) |
| `importance` | INTEGER | 1–10 (default 5) |
| `created_at` | DATETIME | Auto-set |
| `updated_at` | DATETIME | Auto-set |
| `last_accessed` | DATETIME | Updated on read |
| `access_count` | INTEGER | Incremented on read |
| `embedding` | BLOB | Optional vector (for semantic search) |
| `embedding_model` | TEXT | Model used for embedding |
| `tags` | TEXT | JSON array of string tags. Reserved convention: `project:<name>` is auto-appended by `memory_write.py` when a project is active and queried by `protocol_gate.py` to scope the memory cadence per project |
| `context` | TEXT | Free-text context (e.g. run_id) |
| `expires_at` | DATETIME | Optional expiry — enforced by the shared `scope_predicate()` on every read path (SIMP-D2-037) |
| `is_active` | INTEGER | Soft-delete flag |
| `scope` | TEXT | `'global'` or a project name (migration v3, backfilled from `project:<name>` tags). Every read path defaults to active project + global; `--all-projects` widens (SIMP-D2-037) |
| `provenance` | TEXT | Who wrote the entry: `'agent'` (default), `'user'`, `'distiller'`, … (SIMP-D2-037/046) |

### Writers

- `memory_write.py` — manual writes via CLI
- `memory_post_run.py` — auto-called by orchestrator after each run:
  1. Writes an `insight` entry summarising the run
  2. Upserts a rolling-average `fact` entry for model performance

### Readers

- `memory_read.py` — session-start loader (MEMORY.md + daily logs + optional DB entries)
- `hybrid_search.py` — semantic + keyword search across entries

---

## 2. `database/memory/activity.db`

Created by `src/utils/agent_skills/init.py`. Minimal audit trail.

**Scope note:** this database is an optional integration point for *external* PRD-driven
code-generation pipelines (e.g. cornucopia2's `orchestrator.py`, which lives in that project's
own repo — not here). simplex_mind provides the generic hook (`memory_post_run.py` + this
audit table); nothing inside simplex_mind itself writes to it. It is dormant while no
PRD-driven project is running, not dead.

### Tables

| Table | Purpose |
|-------|---------|
| `prd_history` | Write-only audit log of every PRD used in a run |

### `prd_history` columns

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `prd_file` | TEXT | Path to PRD used |
| `prd_hash` | TEXT | SHA-256 of PRD content |
| `output_dir` | TEXT | Where output was written |
| `run_id` | TEXT | Run identifier |
| `created_at` | DATETIME | Auto-set |

### Writers

- An external orchestrator's `record_prd_history()` — one row per run (see scope note above)

### Readers

- None currently. Kept as an audit trail for future analysis.

---

## 3. Ticket databases — per project

Managed by `src/utils/agent_skills/tickets/ticket_db.py`, routed via `project_resolver.py`.

**One database per project:** each project registered in `projects.yaml` has its own DB at
`<project_path>/database/tickets.db`, with its own prefix (e.g. `PROJ`) and counter.
simplex_mind's own `database/tickets.db` is the fallback used on `master` / no active project
(prefix `SIMP`). Resolution order: explicit `--target` → prefix inference from ticket ID →
active project (git branch) → brain DB. `ticket_migrate.py` is the historical one-time script
that split the original shared DB into per-project databases; it is kept for reference only.

**Machine-scoped IDs:** ticket DBs and counters are per-machine, so IDs embed the machine's
identifier (`<PREFIX>-<MACHINE>-NNN`, e.g. `SIMP-L1-042` — `L1` = laptop 1, `D1` = desktop 1)
to stay globally unique. `NNN` is zero-padded to a 3-digit minimum, not a fixed width — the
counter keeps counting past 999 (`SIMP-L1-1000`), and all parsing is digit-count-agnostic. The identifier comes from the top-level `machine:` key in the
gitignored `projects.yaml`; minting fails loudly if it is unset. Legacy `PREFIX-NNN` IDs on a
not-yet-migrated machine are converted in place (DBs, memory tags, daily logs) by the one-time
`tickets/ticket_renumber.py` (`--dry-run` to preview). Legacy IDs in already-pushed git history
are historical records and are not rewritten.

### Tables (identical schema in every ticket DB)

| Table | Purpose |
|-------|---------|
| `tickets` | Bug/feature/task/improvement/documentation tracking |
| `ticket_counter` | Auto-increment counter for the numeric segment of ticket IDs |

### `tickets` columns

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT PK | Format: `<PREFIX>-<MACHINE>-NNN` (e.g. `SIMP-L1-042`; prefix + machine id from projects.yaml; `NNN` = 3-digit minimum, grows past 999) |
| `ticket_type` | TEXT | `bug`, `feature`, `task`, `improvement`, `documentation` |
| `status` | TEXT | `open`, `in_progress`, `blocked`, `done`, `wont_fix` |
| `priority` | TEXT | `low`, `medium`, `high`, `critical` |
| `title` | TEXT | Short description |
| `description` | TEXT | Full details |
| `project` | TEXT | Project name (default `global`) |
| `how_discovered` | TEXT | Manual or auto-detected |
| `created_at` | TEXT | Auto-set |
| `updated_at` | TEXT | Auto-set |
| `resolved_at` | TEXT | Set when status becomes `done` or `wont_fix` |
| `notes` | TEXT | Append-only notes field |

### Writers

- `ticket_create.py` — manual ticket creation
- `memory_post_run.py` → `_check_anomalies()` — auto-creates bug tickets for high fix-cycle files (with dedup against open tickets)

### Readers

- `ticket_list.py` — list/filter tickets (`--all-projects` iterates every project's DB)
- `ticket_read.py` — read single ticket by ID
- `memory_post_run.py` — reads open tickets for dedup before creating new ones
- `session_digest.py` — open/in-progress ticket summary at session start

---

## 4. `database/conversation_history.db`

Managed by `src/utils/agent_skills/conversation/conversation_db.py`.

### Tables

| Table | Purpose |
|-------|---------|
| `sessions` | One row per Claude Code session (UUID, project, timestamps) |
| `messages` | Verbatim transcript messages (role, content, timestamp) |
| `messages_fts` | FTS5 full-text index over message content |
| `ingest_state` | Per-file byte offsets for incremental ingestion |
| `message_usage` | Per-response API token counts (input/output/cache), incl. tool-call-only responses that never reach `messages`; survives Claude Code's ~30-day JSONL cleanup (SIMP-040) **and survives `conversation_purge.py` by default** — token accounting outlives transcript deletion unless `--with-usage` is passed |

### Writers

- `conversation_ingest.py` — parses Claude Code JSONL transcripts (source dirs derived from
  `projects.yaml`); incremental via byte offsets. Triggered by the Stop hook in
  `.claude/settings.json` after every response, plus an optional 5-minute cron as safety net.
- `conversation_purge.py` — deletes `messages` rows by project/age/session (the `messages_ad`
  trigger keeps `messages_fts` consistent), tombstones `sessions` (`message_count = 0`);
  `--with-usage` additionally deletes `message_usage` + the session rows. `ingest_state`
  untouched — byte offsets prevent purged content from silently re-ingesting. See PRIVACY.md.

### Readers

- `conversation_read.py` — list sessions, full transcripts, FTS search, recent messages, stats

---

## Data Flow (external PRD-driven pipeline — dormant unless such a project is active)

```
orchestrator run
    │
    ├─ generate_and_review() → file_infos
    │
    ├─ build_summary() → metrics JSON
    │
    ├─ record_prd_history() ──────────────► activity.db (prd_history)
    │
    └─ memory_post_run.run()
         ├─ _write_run_insight() ─────────► memory.db (memory_entries, type=insight)
         ├─ _check_anomalies() ───────────► tickets.db (bug tickets, with dedup)
         └─ _upsert_model_performance() ──► memory.db (memory_entries, type=fact)
```

---

## Known Limitations

- `prd_history` is write-only — never queried, kept for future audit use
- Daily log sync between disk files and `daily_logs` table is manual (`sync_log_to_db()`)
- Embedding/semantic search returns empty results if embeddings were never generated
- `MEMORY.md` on disk is the primary curated memory; the DB holds structured/searchable entries
- `conversation_purge.py` is irreversible — take a `simplex backup` snapshot first if in doubt

---

## 5. `database/memory/subconscious_index.json` — subconscious retrieval index

Derived, machine-local, gitignored. Built by `subconscious/subconscious_index.py` from the
philosophy pieces in the repo's own `subconscious/` directory (whose frontmatter carries the
committed generic default keywords), merged with this machine's personal trigger keywords
from `database/memory/subconscious_keywords.json` (local, gitignored — personal phrasing is
never committed). Self-contained:
embeds full piece text, so prompt-time recall (`subconscious_recall.py`, UserPromptSubmit
hook) only ever reads this index.

Shape: `{model, built_at, library, pieces: [{name, file, summary, keywords[], source, text,
embedding[384]}]}`. Rebuild after adding or editing pieces or the keyword overlay.

Sibling state file `subconscious_autotune_state.json` (also local, gitignored): the weekly
autotune cron's memory — last run, pending keyword candidates awaiting user review, and the
applied/rejected history that guarantees a phrase is proposed at most once. Journal of all
autotune actions: `logs/subconscious_autotune.log`.

## 6. `database/backups/` — local DB snapshots

`simplex backup` (`src/utils/agent_skills/backup_db.py`) copies memory.db, every ticket DB
(brain + per-project), and conversation_history.db into a timestamped
`database/backups/<YYYYMMDD-HHMMSSZ>/` directory using SQLite's online backup API —
consistent even while hooks/cron hold the DBs open. Gitignored via `database/*`; delete old
snapshot dirs freely (see PRIVACY.md — backups are part of the data-removal story).

Related: `simplex history purge` deletes transcript rows from conversation_history.db
(messages + FTS via trigger, sessions tombstoned) while preserving `message_usage` by
default — token accounting is designed to outlive transcript cleanup.

## 7. `database/config.json` — local onboarding/config state

Written by `init.py` (flag args merge into it; `--mark-onboarded` sets
`"onboarding_complete": true`). **Never committed** — it was untracked in SIMP-D2-021
precisely because a committed `onboarding_complete: true` made every fresh clone skip
SETUP.md onboarding. Its presence/absence drives `doctor.classify_onboarding()`:
present+true = onboarded; missing with no local state = fresh clone (run onboarding);
missing but databases exist = lost config (run `init.py --mark-onboarded`, never
re-onboard). Also holds user-supplied project metadata (name, description, tech stack,
ticket prefix) — see PRIVACY.md.
