# AGENTS.md — simplex_mind Agent Instructions

> This file is read automatically by OpenAI Codex, Cursor, Windsurf, GitHub Copilot Workspace,
> and other tools that look for `AGENTS.md` at the repo root.
> Claude Code users: see `CLAUDE.md` instead.
> Both files reference the same protocol (`AGENT_PROTOCOL.md`) and the same tooling.

---

## Session Start

At the start of every new session:

1. **Load memory:**
   ```bash
   python3 src/utils/agent_skills/memory/memory_read.py --format markdown
   ```

2. **Check open tickets:**
   ```bash
   python3 src/utils/agent_skills/tickets/ticket_list.py --status open
   ```

3. Report ticket count + any critical/high items, then proceed.

---

## Available Tools

All scripts live in `src/utils/agent_skills/`. Run them with `python3` (not `python`).

| Script | Purpose |
|--------|---------|
| `init.py` | Bootstrap `database/` directory, SQLite schemas, and `MEMORY.md` |
| `git_commit.py` | Structured git commits (subcommands: `init`, `status`, `diff`, `commit`) |
| `track_tokens.py` | Optional token usage logging |
| `memory/memory_write.py` | Write a memory entry to daily log + SQLite |
| `memory/memory_read.py` | Load persistent memory at session start |
| `memory/hybrid_search.py` | BM25 + optional vector search over memory |
| `tickets/ticket_create.py` | Create a JIRA-like ticket |
| `tickets/ticket_list.py` | List tickets (filter by status, type, project) |
| `tickets/ticket_read.py` | Read a single ticket by ID |
| `tickets/ticket_update.py` | Update ticket status, priority, or notes |

### Memory commands
```bash
python3 src/utils/agent_skills/memory/memory_write.py \
    --content "..." \
    --type <fact|preference|event|insight|task|relationship> \
    --importance <1-10>

python3 src/utils/agent_skills/memory/memory_read.py --format markdown

python3 src/utils/agent_skills/memory/hybrid_search.py --query "..."
```

### Ticket commands
```bash
python3 src/utils/agent_skills/tickets/ticket_create.py \
    --type <bug|feature|task|improvement|documentation> \
    --title "Short summary" \
    --project <name> \
    --priority <low|medium|high|critical> \
    --description "Full details"

python3 src/utils/agent_skills/tickets/ticket_list.py --status open
python3 src/utils/agent_skills/tickets/ticket_read.py --id PROJECT-001
python3 src/utils/agent_skills/tickets/ticket_update.py \
    --id PROJECT-001 --status <open|in_progress|blocked|done|wont_fix>
```

### Git commands
```bash
python3 src/utils/agent_skills/git_commit.py status
python3 src/utils/agent_skills/git_commit.py diff
python3 src/utils/agent_skills/git_commit.py commit -m "message"
python3 src/utils/agent_skills/git_commit.py commit -m "message" --paths path/to/file.py
```

---

## Ticket Protocol

**Hard rule: Create a ticket before starting any work that edits files.**
`question:` prefixed messages are the only exemption.

**Also create a ticket immediately (without being asked) for:**
1. Bug discovered mid-task
2. Feature or improvement mentioned in passing
3. Topic shifted before resolution
4. Deferred work
5. Anything unexpected — odd behaviour, suspicious code, missing file
6. Memory writes — any time MEMORY.md or the DB is updated as part of a task
7. Task incomplete — work stopped before finishing

---

## Response Summary Block

Append this block after **every** response that makes changes:

```
---
**Git:** committed `<message>` / no commit — <reason>
**Ticket:** created <ID> / updated <ID> / no ticket — <reason>
**DB:** wrote memory / updated ticket db / no db write — <reason>
**Notes:** <warnings, deferred items, anything actionable — omit if nothing>
**Commands:** `feature:` `bug:` `task:` `improvement:` `docs:` `question:`
```

Rules:
- Always include **Git** and **Ticket** lines, even when nothing was done.
- Always include **Commands:** line — it's a persistent cheatsheet for input prefixes.
- Valid "no commit" reasons: read-only task, no source changes, benchmark run.
- Valid "no ticket" reasons: pure conversation, already tracked, trivial one-liner.

---

## Input Prefixes

Prefix messages to lock in the ticket type:

| Prefix | Ticket type | Use when… |
|--------|-------------|-----------|
| `feature:` | feature | Adding new capability |
| `bug:` | bug | Something is broken |
| `task:` | task | Work that doesn't fit above |
| `improvement:` | improvement | Enhancing something that works |
| `docs:` | documentation | Updating docs, AGENTS.md, manifests |
| `question:` | — (none) | Just asking — no work tracked |

`question:` suppresses ticket creation entirely.

---

## Git Branching Workflow

- **`main`** — Stable, production-quality code only. Never commit directly.
- **`develop`** — Integration branch. All feature/fix branches merge here first.
- **`release/<version>`** — Cut from `develop` when ready. Merges into both `main` and `develop`.
- **Feature/fix branches** — Branch from `develop`. Named `feature/<ticket-id>-<slug>` or `fix/<ticket-id>-<slug>`.

**Rules:**
- Never commit directly to `main`, `master`, or `develop` — always use a branch + merge.
- Every branch name must reference a ticket ID.
- Tag `main` after each release merge with `v<major>.<minor>.<patch>`.

---

## Notes for Codex Users

- Use `python3` (not `python`) to run all agent scripts.
- Scripts are self-contained and resolve paths relative to `__file__` — run them from the project root.
- See `AGENT_PROTOCOL.md` for the full specification.
- See `SETUP.md` for one-time onboarding instructions.
