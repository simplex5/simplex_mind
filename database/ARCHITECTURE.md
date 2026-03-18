# Database Architecture

Three SQLite databases power simplex_mind's persistence layer.

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
| `type` | TEXT | `fact`, `preference`, `event`, `insight`, `task`, `relationship` |
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
| `tags` | TEXT | JSON array of string tags |
| `context` | TEXT | Free-text context (e.g. run_id) |
| `is_active` | INTEGER | Soft-delete flag |

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

- `orchestrator.py` → `record_prd_history()` — one row per run

### Readers

- None currently. Kept as an audit trail for future analysis.

---

## 3. `database/tickets.db`

Managed by `src/utils/agent_skills/tickets/ticket_db.py`.

### Tables

| Table | Purpose |
|-------|---------|
| `tickets` | Bug/feature/task/improvement/documentation tracking |
| `ticket_counter` | Auto-increment counter for CORN-NNN IDs |

### `tickets` columns

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT PK | Format: `CORN-NNN` |
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

- `ticket_list.py` — list/filter tickets
- `ticket_read.py` — read single ticket by ID
- `memory_post_run.py` — reads open tickets for dedup before creating new ones

---

## Data Flow

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
