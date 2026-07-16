# AGENTS.md — simplex_mind Brain (Agent Instructions)

> This file provides instructions for AI coding agents (Codex, Cursor, Windsurf, and similar).
> It mirrors the protocols in CLAUDE.md but uses agent-agnostic language.

## Your Behavior

Do not assume the user is right. Think critically about every request. Keep descriptions short.

For all questions you ask the user, immediately elaborate on the choices in layman's terms
so they understand clearly what you're suggesting.

---

## Session Start Protocol

At the start of every new session:

**0. Onboarding check:**
   Check for `database/config.json`. If it is missing or `onboarding_complete` is not `true`,
   follow the onboarding flow in `SETUP.md` instead of the steps below.

1. **Run session digest:**
   ```bash
   python3 src/utils/agent_skills/memory/session_digest.py
   ```
   This outputs: open tickets (count + critical/high), recent decisions, active systems, recent git commits.

2. **Load project config:**
   Read `projects.yaml` in this repo root. Find the project whose `branch:` matches the current simplex_mind git branch (`git branch --show-current`).
   Expand `path` (e.g., `~/projects/my-project`) and read `<path>/<ref_file>` (e.g., the project reference file).
   Follow the project-specific instructions in that file for the remainder of the session.
   **On `master`:** no project is active — report that and proceed with simplex_mind brain tools only (SIMP tickets).

3. **Report readiness:**
   Report the open ticket count, any critical/high items, and confirm which project is active (or that you're on master with no active project).

---

## Project Navigation

```yaml
# projects.yaml — maps project names to paths
machine: L1  # this machine's ticket-ID segment (e.g. L1 = laptop 1, D1 = desktop 1)
projects:
  my-project:
    path: ~/projects/my-project
    ref_file: CLAUDE.md.ref
    ticket_prefix: PROJ
    branch: my-project        # simplex_mind branch for this project
```

- The active project is **derived** from the current simplex_mind git branch: whichever project's `branch:` matches. No flag to toggle.
- **To switch projects:** `git checkout <branch>` in simplex_mind. On `master`, no project is active.
- To add a project: add an entry with `path`, `ref_file`, `ticket_prefix`, and `branch`.

---

## Working Directory

simplex_mind is the launch directory, but most work happens in the active project.

- **Tickets, memory, conversation:** Always use simplex_mind's tools (centralized in this repo).
- **Git operations on project code:** Use native git commands in the project directory:
  ```bash
  cd ~/projects/my-project  # or whatever projects.yaml says
  git add <files>
  git commit -m "type: description (PROJ-L1-NNN)"
  # Only when isolation is needed (see Branching Workflow):
  git checkout -b feature/PROJ-L1-NNN-slug
  ```
- **Git operations on simplex_mind itself:** Use `git_commit.py` (rare — only when editing brain tools).
- **File edits:** Use absolute paths to the project directory (from projects.yaml).

---

## Memory Protocol

**Load at session start:**
```bash
python3 src/utils/agent_skills/memory/memory_read.py --format markdown
```

**Write a memory entry:**
```bash
python3 src/utils/agent_skills/memory/memory_write.py \
    --content "..." \
    --type <fact|preference|event|insight|task|relationship|decision|note> \
    --importance <1-10>
```

**Write with ticket cross-reference:**
```bash
python3 src/utils/agent_skills/memory/memory_write.py \
    --content "..." --type decision --ticket PROJ-L1-042
```

**Search memory:**
```bash
python3 src/utils/agent_skills/memory/hybrid_search.py --query "..."
```

**Sync MEMORY.md from database:**
```bash
python3 src/utils/agent_skills/memory/memory_sync.py          # regenerate
python3 src/utils/agent_skills/memory/memory_sync.py --dry-run # preview
```

**Direct MEMORY.md edits** (for curated, human-readable notes):
- Read and edit `database/memory/MEMORY.md` directly.
- Keep it under ~200 lines; content beyond that may be truncated from context.
- Organise by topic, not chronologically. Remove outdated entries promptly.

**Systems inventory** (`database/memory/systems.md`):
- Registry of significant features and systems across all projects.
- Update when creating, removing, or significantly changing a system.
- Read by session_digest.py for the "Active Systems" section.

---

## Subconscious — Context-Triggered Reasoning Philosophy

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

---

## Ticket Protocol

**Location:** Per-project: `<project_path>/database/tickets.db`
Ticket IDs are machine-scoped: `PREFIX-<MACHINE>-NNN` (e.g. `SIMP-L1-042`), where MACHINE comes from the top-level `machine:` key in projects.yaml — each machine mints in its own namespace so IDs never collide across computers.
Tickets auto-target the active project. Use `--target <name>` to override.
Ticket ID prefix is auto-inferred for read/update operations (e.g. PROJ-L1-122 → my-project).
On `master` (no active project), tickets fall through to simplex_mind's own `database/tickets.db` under prefix `SIMP`.

**Commands:**
```bash
# Create (targets active project by default)
python3 src/utils/agent_skills/tickets/ticket_create.py \
    --type <bug|feature|task|improvement|documentation> \
    --title "Short summary" \
    --project <name> \
    --priority <low|medium|high|critical> \
    --description "Full details"
# Create targeting a specific project
python3 src/utils/agent_skills/tickets/ticket_create.py \
    --type task --title "..." --target other-project

# Read / list
python3 src/utils/agent_skills/tickets/ticket_read.py --id PROJ-L1-001
python3 src/utils/agent_skills/tickets/ticket_list.py --status open
python3 src/utils/agent_skills/tickets/ticket_list.py --all
python3 src/utils/agent_skills/tickets/ticket_list.py --target other-project
python3 src/utils/agent_skills/tickets/ticket_list.py --all-projects

# Update (auto-infers project from ticket ID prefix)
python3 src/utils/agent_skills/tickets/ticket_update.py \
    --id PROJ-L1-001 --status <open|in_progress|blocked|done|wont_fix>
python3 src/utils/agent_skills/tickets/ticket_update.py \
    --id PROJ-L1-001 --priority high --note "Context note"
```

### Ambiguous ticket queries

**Hard rule: When the user asks about tickets without explicitly naming a project, ask which project they mean. Do not guess or scan a default — ask first.**

### When to create tickets

**Hard rule: Create a ticket before starting any work that edits files.**
No exceptions. `question:` prefix is the only exemption.

Also create a ticket immediately for:
1. Bug discovered mid-task
2. Feature or improvement requested
3. Topic shifted before resolution
4. Deferred by choice
5. Anything unexpected observed
6. Memory writes as part of a task
7. Task incomplete — work stopped before finishing

### Session triggers

- **Start**: run `ticket_list.py --status open` (targets active project by default), report count + critical/high items.
- **Scoping rule**: Only use `--all-projects` when on the main simplex_mind branch (no active project). When a project is active, all ticket queries scope to that project only.
- **During work**: create tickets as issues surface — do not batch at the end.
- **End**: summarise tickets created this session by ID and title.

---

## Conversation History Protocol

**Ingest** — runs automatically via cron every 5 minutes. (Claude Code additionally runs ingestion via a Stop hook in `.claude/settings.json` after every response — see CLAUDE.md; other agents rely on the cron job.)
```bash
python3 src/utils/agent_skills/conversation/conversation_ingest.py
```
Scans JSONL files from `~/.claude/projects/*/` for all registered projects.

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

**Stats:**
```bash
python3 src/utils/agent_skills/conversation/conversation_read.py --action stats
```

Ingestion also captures per-response API token usage into the `message_usage` table
(input/output/cache counts — including tool-call-only responses), so token accounting
survives Claude Code's ~30-day transcript cleanup. Lifetime totals + per-month breakdown
are included in `--action stats`.

---

## Input Prefixes — Intent Signals

Prefix your message to lock in the ticket type and skip inference:

| Prefix | Ticket type | Use when... |
|--------|-------------|-------------|
| `feature:` | feature | Adding new capability |
| `bug:` | bug | Something is broken |
| `task:` | task | Work that doesn't fit the above |
| `improvement:` | improvement | Enhancing something that already works |
| `docs:` | documentation | Updating docs, manifests |
| `question:` | — (no ticket) | Just asking — no work to track |

**Rules:**
- When a prefix is present: ticket type is locked, ticket created at start of work, prefix stripped.
- When no prefix is present: existing inference rules apply.
- `question:` suppresses ticket creation entirely.

---

## Response Summary

After **every** response that makes changes, append:

```
---
**Branch:** on `develop` / created `feature/PROJ-L1-NNN`
**Commit:** `<message>` / no commit — <reason>
**Ticket:** created <ID> / updated <ID> / no ticket — <reason>
**DB:** wrote memory / updated ticket db / no db write — <reason>
**Notes:** <warnings, deferred items — omit if nothing>
**Commands:** `feature:` `bug:` `task:` `improvement:` `docs:` `question:`
```

Rules:
- Always include **Branch**, **Commit**, and **Ticket** lines, even when the answer is "nothing done".
- Always include **DB** line.
- **Notes** is optional — only include if something actionable or surprising.
- Always include **Commands:** as a persistent cheatsheet.
- Keep each line to one sentence.

---

## Git Maintenance

### Branching Workflow

- **`main`** / **`master`** — Stable. Never commit directly.
- **`develop`** — Default working branch. Most work is committed here directly.
- **Feature/fix branches** — For work that needs isolation. Named `<type>/<ticket-id>-<slug>`.

Commits always happen. The only decision is whether to create a new branch first.

**Branch when:**
- The work is experimental, risky, or might be abandoned
- Multiple tasks are in progress and could conflict
- The user explicitly requests a branch
- The work needs a clean revert path (large refactors, migrations)

**Stay on the current branch when:**
- It is sequential progress on an already-isolated line of work
- The work is straightforward and will definitely be kept

**Decision test:** "Does this work need to be isolated before it lands on the working branch?" If yes → branch. Otherwise → commit to the current branch.

**Rules:**
- Never commit directly to main/master — always merge from develop or a branch.
- Always create a ticket before any file edits — branching is conditional, tickets are not.
- Every branch name must reference a ticket ID.

**Commands (simplex_mind repo only):**
```bash
python3 src/utils/agent_skills/git_commit.py init      # one-time: git init + first framework commit
python3 src/utils/agent_skills/git_commit.py status
python3 src/utils/agent_skills/git_commit.py diff
python3 src/utils/agent_skills/git_commit.py commit -m "message"
```

These commands operate on **simplex_mind's own repo**. For project repos (e.g., my-project),
use native git commands in the project directory — see [Working Directory](#working-directory).

**Commit automatically after:**
- Running `init.py` for the first time
- Writing or updating any file in `src/`
- Modifying `AGENTS.md` or `database/memory/MEMORY.md`

**Never commit:**
- `projects.yaml` — local config, gitignored
- Benchmark runs — output is gitignored
- Edits to `database/memory/logs/` or `database/*.db` — local session state

---

## Guardrails — Learned Behaviors

- Always check `src/utils/agent_skills/manifest.md` before writing a new script.
- Create a ticket before any file edits — no exceptions. Branching is conditional (see Branching Workflow).
- When branching, always branch from the current working branch.
- Verification steps in plans must not require running scripts — confirm by inspecting file contents and diffs only.
- Before updating any documentation file that is not the immediate subject of the current task, ask the user.
- When improving any file derived from a shared template, identify all sibling files. Confirm with the user before updating each.
- Keep framework tools generic. Domain-specific knowledge belongs only in project PRDs and hardprompts.
- Update `database/memory/systems.md` when creating, removing, or significantly changing a system.
- Plans must include a Maintenance section listing: ticket ID, branch decision (stay or create), and commit strategy.
- When the user asks about tickets without explicitly naming a project, ask which project. Never guess — wastes tokens scanning wrong DBs.
- `projects.yaml` is local config (gitignored). Never commit it. The active project is derived from the current simplex_mind git branch — to switch projects, just `git checkout <branch>`.

*(Add new guardrails as mistakes happen. Keep this under 15 items.)*

---

## File Structure — Where Things Live

```
simplex_mind/                          <- brain repo (agent launches here)
|-- CLAUDE.md                          <- Claude Code instructions
|-- AGENTS.md                          <- this file — Codex/Cursor/Windsurf instructions
|-- projects.yaml                      <- maps project names -> paths (local, gitignored)
|-- subconscious/                      <- reasoning-philosophy piece library (canonical, committed)
|-- database/
|   |-- memory/
|   |   |-- memory.db                  <- structured memory (SQLite)
|   |   |-- activity.db                <- audit trail
|   |   |-- MEMORY.md                  <- curated persistent memory
|   |   |-- systems.md                 <- system inventory
|   |   +-- logs/                      <- daily logs (YYYY-MM-DD.md)
|   |-- tickets.db                     <- brain (SIMP) tickets — each project has its own <project>/database/tickets.db
|   |-- conversation_history.db        <- conversation transcripts + token usage
|   +-- ARCHITECTURE.md                <- database schema docs
+-- src/utils/agent_skills/
    |-- memory/                        <- memory tools
    |-- tickets/                       <- ticket tools
    |-- conversation/                  <- conversation history tools
    |-- subconscious/                  <- context-triggered philosophy: index, recall hook, miner
    |-- git_commit.py                  <- git operations
    |-- init.py                        <- project bootstrapper
    |-- project_resolver.py            <- branch -> project resolution, ticket DB routing
    |-- track_tokens.py                <- token metrics logger (optional)
    +-- manifest.md                    <- tool inventory
```

---

## Your Job in One Sentence

Load the session digest, read the active project's instructions, then be direct, reliable, and get things done.
