# Agent Protocol — Ticketing, Memory & Git

Drop this file (and the scripts below) into any project to give Claude persistent memory,
issue tracking, and structured git commit behaviour.

---

## 1. Prerequisites

- Python 3.10+
- Git repository initialised
- Copy the following scripts into your project:
  ```
  src/utils/agent_skills/
    init.py
    git_commit.py
    memory/
      memory_db.py
      memory_read.py
      memory_write.py
      hybrid_search.py
    tickets/
      ticket_db.py
      ticket_create.py
      ticket_read.py
      ticket_update.py
      ticket_list.py
  ```

---

## 2. Install dependencies

```bash
pip install python-dotenv
# Optional — enables semantic memory search:
# pip install openai numpy rank_bm25
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
- `database/tickets.db` — SQLite: issue tracker
- `logs/` and `.tmp/` — runtime directories

Then create the first commit:
```bash
python src/utils/agent_skills/git_commit.py init
```

---

## 4. Protocol — Rules Claude must follow

### 4.1 Ticket Protocol

**Hard rule: Create a ticket before starting any work that edits files.**
No exceptions. Pure questions (using the `question:` prefix) are the only exemption.

**Commands:**
```bash
# Create
python src/utils/agent_skills/tickets/ticket_create.py \
    --type <bug|feature|task|improvement|documentation> \
    --title "Short summary" \
    --project <name> \
    --priority <low|medium|high|critical> \
    --description "Full details"

# Read / list
python src/utils/agent_skills/tickets/ticket_read.py --id PROJECT-001
python src/utils/agent_skills/tickets/ticket_list.py --status open
python src/utils/agent_skills/tickets/ticket_list.py --all

# Update
python src/utils/agent_skills/tickets/ticket_update.py \
    --id PROJECT-001 --status <open|in_progress|blocked|done|wont_fix>
python src/utils/agent_skills/tickets/ticket_update.py \
    --id PROJECT-001 --priority high --note "Context note"
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
    --type <fact|preference|event|insight|task|relationship> \
    --importance <1-10>
```

**Search memory:**
```bash
python src/utils/agent_skills/memory/hybrid_search.py --query "..."
```

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

## 5. Input Prefixes

Prefix messages to lock in the ticket type and skip inference:

| Prefix | Ticket type | Use when… |
|--------|-------------|-----------|
| `feature:` | feature | Adding new capability |
| `bug:` | bug | Something is broken |
| `task:` | task | Work that doesn't fit above |
| `improvement:` | improvement | Enhancing something that works |
| `docs:` | documentation | Updating docs, CLAUDE.md, manifests |
| `question:` | — (none) | Just asking — no work tracked |

When a prefix is present: ticket is created at the start, prefix stripped before processing.
`question:` suppresses ticket creation entirely.

---

## 6. Schema Reference

**Ticket fields:** `id` (PROJECT-NNN), `type`, `status`, `priority`, `title`, `description`, `project`, `notes`, `created_at`, `updated_at`, `resolved_at`

**Ticket types:** `bug` · `feature` · `task` · `improvement` · `documentation`

**Ticket statuses:** `open` · `in_progress` · `blocked` · `done` · `wont_fix`

**Ticket priorities:** `low` · `medium` · `high` · `critical`

**Memory types:** `fact` · `preference` · `event` · `insight` · `task` · `relationship`

**Memory importance:** 1–10 (default 5). Higher = surfaced more prominently in search.
