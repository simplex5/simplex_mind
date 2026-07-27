# agent_skills/ — Skills Manifest

All tools agents and humans invoke — by script path (canonical, always works) or via the
installed `simplex` CLI. CI (`.github/workflows/ci.yml`) runs `ruff` + `pytest` on every
push: a new tool needs a test.

---

## Core Tools

| Tool | File | Description |
|------|------|-------------|
| Token Tracker | `track_tokens.py` | Appends call objects to metrics JSON (optional — consumed by a user-side statusline script outside this repo) |
| Git Operations | `git_commit.py` | Init, status, commit, diff for framework files |
| Initializer | `init.py` | Creates full project scaffold (idempotent); `--mark-onboarded` re-marks onboarding after the config-untracking migration |
| Doctor | `doctor.py` | Health validation for the whole brain: 11 checks (onboarding, projects.yaml, DBs, index, autotune, venv, hooks, git identity, branch mapping) with per-check remediation; `--status` compact page, exit 1 when degraded; exports `classify_onboarding()` (fresh clone vs lost config), reused by session_digest |
| Backup | `backup_db.py` | `simplex backup` — SQLite online-backup of memory.db, all tickets DBs, conversation_history.db to timestamped `database/backups/<UTC>/` (gitignored); safe while DBs are in use |
| simplex CLI | `../../simplex_cli/cli.py` | Installed `simplex` command (`pip install -e .`) — thin dispatcher over these tools: ticket/memory/history/digest/doctor/status/backup + `project use` (git-checkout wrapper). Script paths stay canonical for hooks and other agents; `py -m simplex_cli` (via `__main__.py`) works as an uninstalled fallback |
| Shared Helpers | `_common.py` | Single source for repo paths (REPO_ROOT/DATABASE_DIR/MEMORY_DIR), row_to_dict, ticket priority ordering, standard CLI epilogue (cli_finish), optional dotenv loading |
| Project Resolver | `project_resolver.py` | Shared utility for resolving project config from projects.yaml; routes ticket operations to per-project databases |

---

## memory/ — Persistent Memory Tools

| Tool | File | Description |
|------|------|-------------|
| Memory DB | `memory/memory_db.py` | SQLite CRUD for persistent memory entries (types: fact, preference, event, insight, task, relationship, decision) |
| Memory Reader | `memory/memory_read.py` | Load MEMORY.md + systems.md + daily logs at session start |
| Memory Writer | `memory/memory_write.py` | Append to daily logs and SQLite; supports `--ticket` cross-reference; auto-appends a `project:<name>` tag to DB rows when a project is active (the tag protocol_gate's cadence check queries) |
| Memory Sync | `memory/memory_sync.py` | Update the marker-delimited AUTO-SYNC block in MEMORY.md from memory.db; all hand-curated content outside the block is preserved verbatim |
| Session Digest | `memory/session_digest.py` | Focused session-start context: open tickets, decisions, systems, git log (< 200 lines); broken subsystems render as `UNAVAILABLE — <reason>` (never a false `Open: 0`); prints `CONFIG LOST` / `ONBOARDING INCOMPLETE` self-heal lines via doctor's `classify_onboarding()` |
| Embedding Gen | `memory/embed_memory.py` | Vector embeddings for semantic search (optional OpenAI) |
| Semantic Search | `memory/semantic_search.py` | Cosine similarity search over embeddings |
| Hybrid Search | `memory/hybrid_search.py` | Combined BM25 + vector search |
| Post-Run Writer | `memory/memory_post_run.py` | Reads metrics JSON after each run; writes insight entry, upserts model-performance fact, creates anomaly tickets |
| Protocol Gate | `memory/protocol_gate.py` | UserPromptSubmit hook: deterministic protocol enforcement — nags when 5+ tickets resolved since last memory write (scoped per project via `project:<name>` tags, global fallback until the first tagged write), re-surfaces pending autotune candidates mid-session, detects auto-memory-instead-of-memory.db substitution; read-only, throttled, always fail-open; prints a visible `[protocol-gate: …]` marker when it fires and a once-per-session `[protocol-gate degraded: …]` marker when a check errors |

---

## tickets/ — Ticket Tracking Tools

| Tool | File | Description |
|------|------|-------------|
| Ticket DB | `tickets/ticket_db.py` | SQLite CRUD core for per-project ticket tracking; prefix resolved from projects.yaml via project_resolver; supports `--target` routing |
| Ticket Create | `tickets/ticket_create.py` | CLI: create a ticket (type, title, project, priority, description, --target) |
| Ticket Update | `tickets/ticket_update.py` | CLI: update status, priority, notes, title, description (--target or auto-infer from ID prefix) |
| Ticket List | `tickets/ticket_list.py` | CLI: list/filter tickets by status, type, project, priority (--target, --all-projects) |
| Ticket Read | `tickets/ticket_read.py` | CLI: get full detail for a single ticket by ID (--target or auto-infer from ID prefix) |
| Ticket Migrate | `tickets/ticket_migrate.py` | One-time migration from shared tickets.db to per-project databases (historical; keep for reference) |
| Ticket Renumber | `tickets/ticket_renumber.py` | One-time migration of legacy PREFIX-NNN ids to machine-scoped PREFIX-<MACHINE>-NNN across ticket DBs, memory.db, and daily logs (`--dry-run` to preview; run once per machine) |

---

## subconscious/ — Context-Triggered Reasoning Philosophy

| Tool | File | Description |
|------|------|-------------|
| Subconscious Indexer | `subconscious/subconscious_index.py` | Embeds philosophy pieces from the repo's `subconscious/` directory (frontmatter = generic default keywords), merged with the local personal keyword overlay (`database/memory/subconscious_keywords.json`, gitignored), into `database/memory/subconscious_index.json`; re-run after editing pieces or keywords (`--list` to inspect) |
| Subconscious Recall | `subconscious/subconscious_recall.py` | UserPromptSubmit hook: matches each prompt against the index (keywords primary, cosine ≥0.70 rescue), injects ≤2 matching pieces as context, once per session each; always fail-open; prints a visible `[subconscious: …]` marker line when pieces fire |
| Subconscious Miner | `subconscious/subconscious_mine.py` | Mines conversation_history.db user prompts against the index: coverage, keyword gaps, new-group candidate clusters, uncovered n-grams; markdown report for curation (`--db`, `--since`, `--out`) |
| Subconscious Autotune | `subconscious/subconscious_autotune.py` | Weekly cron: mines gated keyword candidates (support/precision/fire-rate admission gates) into a pending queue for in-session review — nothing applied without approval (`--review`, `--approve`, `--reject`, `--dry-run`); state + journal machine-local |

---

## conversation/ — Conversation History Tools

| Tool | File | Description |
|------|------|-------------|
| Conversation DB | `conversation/conversation_db.py` | SQLite CRUD + FTS5 for verbatim conversation transcripts |
| Conversation Ingester | `conversation/conversation_ingest.py` | Parse Claude Code JSONL files into conversation_history.db; multi-source directory support; captures per-response token usage; cron-friendly |
| Conversation Reader | `conversation/conversation_read.py` | CLI: list sessions, get transcript, full-text search, recent messages, stats incl. token totals + per-month breakdown |
| Conversation Purge | `conversation/conversation_purge.py` | Delete stored transcripts by project/age/session (`simplex history purge`); preserves token usage by default, requires --yes, see PRIVACY.md |
