# agent_skills/ — Skills Manifest

All tools and reference files Claude invokes directly.

---

## Core Tools

| Tool | File | Description |
|------|------|-------------|
| Token Tracker | `track_tokens.py` | Appends call objects to metrics JSON (optional — requires statusline.sh) |
| Git Operations | `git_commit.py` | Init, status, commit, diff for framework files |
| Initializer | `init.py` | Creates full project scaffold (idempotent) |
| Project Resolver | `project_resolver.py` | Shared utility for resolving project config from projects.yaml; routes ticket operations to per-project databases |

---

## memory/ — Persistent Memory Tools

| Tool | File | Description |
|------|------|-------------|
| Memory DB | `memory/memory_db.py` | SQLite CRUD for persistent memory entries (types: fact, preference, event, insight, task, relationship, decision) |
| Memory Reader | `memory/memory_read.py` | Load MEMORY.md + systems.md + daily logs at session start |
| Memory Writer | `memory/memory_write.py` | Append to daily logs and SQLite; supports `--ticket` cross-reference |
| Memory Sync | `memory/memory_sync.py` | Regenerate MEMORY.md from memory.db (preserves ## Pinned section) |
| Session Digest | `memory/session_digest.py` | Focused session-start context: open tickets, decisions, systems, git log (< 200 lines) |
| Embedding Gen | `memory/embed_memory.py` | Vector embeddings for semantic search (optional OpenAI) |
| Semantic Search | `memory/semantic_search.py` | Cosine similarity search over embeddings |
| Hybrid Search | `memory/hybrid_search.py` | Combined BM25 + vector search |
| Post-Run Writer | `memory/memory_post_run.py` | Reads metrics JSON after each run; writes insight entry, upserts model-performance fact, creates anomaly tickets |

---

## tickets/ — Ticket Tracking Tools

| Tool | File | Description |
|------|------|-------------|
| Ticket DB | `tickets/ticket_db.py` | SQLite CRUD core for per-project ticket tracking; prefix resolved from projects.yaml via project_resolver; supports `--target` routing |
| Ticket Create | `tickets/ticket_create.py` | CLI: create a ticket (type, title, project, priority, description, --target) |
| Ticket Update | `tickets/ticket_update.py` | CLI: update status, priority, notes, title, description (--target or auto-infer from ID prefix) |
| Ticket List | `tickets/ticket_list.py` | CLI: list/filter tickets by status, type, project, priority (--target, --all-projects) |
| Ticket Read | `tickets/ticket_read.py` | CLI: get full detail for a single ticket by ID (--target or auto-infer from ID prefix) |

---

## conversation/ — Conversation History Tools

| Tool | File | Description |
|------|------|-------------|
| Conversation DB | `conversation/conversation_db.py` | SQLite CRUD + FTS5 for verbatim conversation transcripts |
| Conversation Ingester | `conversation/conversation_ingest.py` | Parse Claude Code JSONL files into conversation_history.db; multi-source directory support; cron-friendly |
| Conversation Reader | `conversation/conversation_read.py` | CLI: list sessions, get transcript, full-text search, recent messages, stats |
