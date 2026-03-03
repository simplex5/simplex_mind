# claude_code_skills/ — Skills Manifest

All tools and reference files Claude invokes directly.

---

## Core Tools

| Tool | File | Description |
|------|------|-------------|
| Token Tracker | `track_tokens.py` | Appends call objects to metrics JSON (optional — requires statusline.sh) |
| Git Operations | `git_commit.py` | Init, status, commit, diff for framework files |
| Initializer | `init.py` | Creates full project scaffold (idempotent) |

---

## memory/ — Persistent Memory Tools

| Tool | File | Description |
|------|------|-------------|
| Memory DB | `memory/memory_db.py` | SQLite CRUD for persistent memory entries |
| Memory Reader | `memory/memory_read.py` | Load MEMORY.md + daily logs at session start |
| Memory Writer | `memory/memory_write.py` | Append to daily logs and SQLite |
| Embedding Gen | `memory/embed_memory.py` | Vector embeddings for semantic search (optional OpenAI) |
| Semantic Search | `memory/semantic_search.py` | Cosine similarity search over embeddings |
| Hybrid Search | `memory/hybrid_search.py` | Combined BM25 + vector search |
| Post-Run Writer | `memory/memory_post_run.py` | Reads metrics JSON after each run; writes insight entry, upserts model-performance fact, creates anomaly tickets |

---

## tickets/ — Ticket Tracking Tools

| Tool | File | Description |
|------|------|-------------|
| Ticket DB | `tickets/ticket_db.py` | SQLite CRUD core for persistent ticket tracking (prefix config-driven via `database/config.json`, falls back to PROJECT) |
| Ticket Create | `tickets/ticket_create.py` | CLI: create a ticket (type, title, project, priority, description) |
| Ticket Update | `tickets/ticket_update.py` | CLI: update status, priority, notes, title, description |
| Ticket List | `tickets/ticket_list.py` | CLI: list/filter tickets by status, type, project, priority |
| Ticket Read | `tickets/ticket_read.py` | CLI: get full detail for a single ticket by ID |
