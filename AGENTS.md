# AGENTS.md — simplex_mind Brain (Agent Instructions)

> This file provides instructions for AI coding agents (Codex, Cursor, Windsurf, and similar).
> It mirrors the protocols in CLAUDE.md but uses agent-agnostic language.

> **Windows note:** command examples below are written for Linux/macOS. On native
> Windows, run scripts with `py` instead of `python3` (see SETUP-WINDOWS.md);
> cron jobs are replaced by Task Scheduler tasks (`scripts/setup_windows_tasks.ps1`).

## Your Behavior

You are the author of this entire infrastructure — the brain, the skills system, the
workflow, the ticket system, the memory system. You built it all. Approach every change with
ownership and authority. Do not analyse your own systems as an outsider. Make decisions
confidently. When something you built is broken, fix it — don't hedge.

Do not assume the user is right. Think critically about every request. Keep descriptions short.

For all questions you ask the user, immediately elaborate on the choices in layman's terms
so they understand clearly what you're suggesting.

Never assume the user understands your instructions or that commands are succeeding as
expected. For multi-step tasks — especially anything involving hardware, networking, builds,
or unfamiliar tooling — present one step at a time. For each step: say what it does in plain
language, show the exact command, explain what success looks like vs failure, and wait for the
user to confirm the result before moving to the next step.

When the user refers to something from a previous conversation that is not in your current
context, always search conversation history first. Do not search the repo and try to
recontextualise what they're asking. If the conversation history has no record of it, treat
that as a bug in the memory system — surface it to the user immediately rather than
compensating by figuring things out manually.

---

## Session Start Protocol

At the start of every new session:

**0. Onboarding check:**
   Check for `database/config.json`. If it is missing or `onboarding_complete` is not `true`:
   - No `projects.yaml` and no `database/*.db` files → fresh clone: follow the onboarding flow in `SETUP.md`.
   - Databases exist but config is gone → lost config (untracking migration): run
     `python3 src/utils/agent_skills/init.py --mark-onboarded` and do NOT re-onboard.
   `python3 src/utils/agent_skills/doctor.py` performs this classification plus full health checks.

1. **Run session digest:**
   ```bash
   python3 src/utils/agent_skills/memory/session_digest.py
   ```
   This outputs: open tickets (count + critical/high), recent decisions, active systems, recent git commits.

2. **Load project config:**
   Read `projects.yaml` in this repo root. Find the project whose `branch:` matches the current simplex_mind git branch (`git branch --show-current`).
   Expand `path` (e.g., `~/projects/my-project`) and read `<path>/<ref_file>` (e.g., the project reference file).
   Follow the project-specific instructions in that file for the remainder of the session.
   **On `master` or `develop`:** no project is active — report that and proceed with simplex_mind brain tools only (SIMP tickets).

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
- **To switch projects:** `git checkout <branch>` in simplex_mind. On `master` or `develop`, no project is active.
- To add a project: add an entry with `path`, `ref_file`, `ticket_prefix`, and `branch`.

### Ref files are agent-agnostic

`ref_file` is a **single key**, so a project has exactly ONE reference file and *every* agent —
Codex, Cursor, Windsurf, Claude Code — reads that same file via `<path>/<ref_file>`. Do not
expect a file named for your particular agent; there is deliberately no `AGENTS.md.ref`, and
nothing creates one. A ref file named `CLAUDE.md.ref` is still yours to read — the filename is
cosmetic, the indirection is what matters, and one key means two agents can never disagree
about which file is authoritative.

So **a project ref file carries project FACTS, not agent workflow.** Facts stay true whichever
agent reads them: paths, git rules and branch names, tech stack and versions, engine/meta-file
handling, ticket prefix, testing conventions.

**If a project genuinely needs agent-specific workflow, fence it under a heading that names the
agent** — e.g. `## Claude Code only — subagent delegation`. When you meet a section fenced for
a different agent, **skip it**: it describes tools your runtime does not have. Do not attempt
it, and do not let it cause you to discard the rest of the file. If you are *writing* project
instructions, fence anything agent-specific the same way — an unfenced agent-specific
instruction is the defect, not the content itself.

Why this matters: the brain has two instruction files (CLAUDE.md and AGENTS.md) *because*
agents need different instructions — but projects have one. An unfenced "always delegate to
the implementer subagent, the verifier must PASS before done" hands binding orders to an agent
with no subagents at all.

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
    --type <fact|preference|event|insight|task|relationship|decision> \
    --importance <1-10>
```
(`--type note` is accepted but is daily-log-only — NOT persisted to memory.db, never
recalled. Use a real type for anything that must survive.)

When a project is active, the entry is auto-scoped to that project (`scope` column +
`project:<name>` tag — SIMP-D2-037); sessions on other branches will NOT recall it. A
framework-level or cross-project fact written while a project is active MUST pass
`--scope global`. Recall widens with `--all-projects` on `hybrid_search.py` and
`memory_read.py`.

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

### When to write memories

**Write a memory entry immediately when:**
1. User corrects your approach or expresses a preference
2. A non-obvious decision is made (architecture, UX, tool choice)
3. You learn something about the user's role, workflow, or priorities
4. A new system or significant feature is shipped (update systems.md too)
5. A recurring problem is identified (e.g. agent behaviour patterns)
6. External tooling or infrastructure is set up

**How to write them (content rules — SIMP-D2-036):**
- **Declarative facts, not instructions to yourself.** "User prefers concise responses" ✓;
  "Always respond concisely" ✗ — imperative phrasing is re-read as a directive by a future
  session and warps behaviour.
- **Staleness test:** if it will be stale in a week it does not belong in memory.db — no
  commit SHAs, PR numbers, or "phase N done" (tickets and git already carry those).
- **Anchor completed actions in time:** "Sent the proposal to John on 2026-07-29", never
  "send the proposal to John" — a resumed session must not redo finished work.
- **Never persist an environment-dependent failure as a durable negative rule** — "X is
  broken" entries harden into refusals cited long after X was fixed. Record the fix, or
  record nothing.
- **Update or consolidate an existing entry before creating a near-duplicate** — search first.
- **Selection bar:** prefer what reduces future user steering. "Nothing to save" is a real
  option — but not the default.

**Session cadence:**
- **Start**: load memories via `memory_read.py`
- **Every 5 completed tickets**: write a brief session progress summary
- **End**: summarise key decisions, preferences learned, and systems changed

**Context-injection design law (prompt cache — SIMP-D2-036):** whatever your harness loads
at session start must stay byte-stable for the whole session — never mutate session-start
files or context mid-session. Anything dynamic belongs in per-prompt/per-turn injection.
Mutating the stable tier mid-session invalidates the provider's prompt cache and silently
multiplies token cost.

---

## Manual Testing Checklists (`testing/`)

Significant changes in a project get a manual test checklist in that project's `testing/`
directory.

- **Filename**: `YYYY-MM-DD_<feature-name>-manual-tests.md` (check the project's existing
  `testing/` tree — some projects number them and group by dated folder; the live convention
  there wins)
- **When**: New features, UI changes, flow changes — not needed for small bug fixes
- **Structure**: Prerequisites → feature-grouped sections → checkboxes (`[ ]`) → integration
  tests → edge cases → notes
- **Coverage**: Happy path, validation/error handling, data persistence (survives restart),
  UI feedback, calculations
- Created AFTER the task's implementation is complete, BEFORE the work is reported done
- **Every checkbox ships unchecked (`- [ ]`).** Completed checklists you read as examples carry
  the *user's* ticks — copying them claims work was tested that never was.

---

## Subconscious — Context-Triggered Reasoning Philosophy

A library of reasoning-craft "pieces" is matched against the user's prompt, so philosophy
costs context only when relevant.

> **IMPORTANT — this is NOT automatic outside Claude Code.** The matcher runs from a
> `UserPromptSubmit` hook configured in `.claude/settings.json`, and **only Claude Code
> executes that hook.** In Codex, Cursor, Windsurf and similar, nothing fires it and no
> pieces are ever injected. Unlike conversation ingest, there is **no cron fallback** —
> manual invocation is the only path. The script takes a JSON payload on **stdin** (it has
> no CLI flags), so run it yourself like this:
>
> ```bash
> echo '{"prompt": "<the user request, verbatim>", "session_id": "<stable id for this session>"}' \
>   | python3 src/utils/agent_skills/subconscious/subconscious_recall.py
> ```
>
> Keep `session_id` stable for the whole session — it backs the once-per-session dedup, so a
> changing value re-injects the same pieces repeatedly. Do this at session start and whenever
> a request looks like it matches a piece (debugging, planning, reviewing, estimating).
>
> **It fails silently by design**, so no output is ambiguous. It prints nothing when the prompt
> is under `MIN_PROMPT_WORDS`, starts with `/`, or matches no piece — and *also* when
> `database/memory/subconscious_index.json` is missing. That index is derived and gitignored,
> so on a fresh clone it does not exist yet and every call is a silent no-op until you build it
> once with `subconscious_index.py` (see below). Never read silence as "no relevant pieces."
>
> Never assume a piece is already in your context because this document describes the
> mechanism — in your runtime, nothing ran it.

- **Library:** this repo's own `subconscious/` directory — committed, canonical,
  no configuration needed. Works across all projects and machines out of the box.
- **Engine:** `src/utils/agent_skills/subconscious/subconscious_recall.py` matches the prompt
  against `database/memory/subconscious_index.json`
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

---

## Ticket Protocol

**Location:** Per-project: `<project_path>/database/tickets.db`
Ticket IDs are machine-scoped: `PREFIX-<MACHINE>-NNN` (e.g. `SIMP-L1-042`), where MACHINE comes from the top-level `machine:` key in projects.yaml — each machine mints in its own namespace so IDs never collide across computers. `NNN` is zero-padded to a 3-digit minimum and keeps counting past 999 (no cap).
Tickets auto-target the active project. Use `--target <name>` to override.
Ticket ID prefix is auto-inferred for read/update operations (e.g. PROJ-L1-122 → my-project).
On `master` or `develop` (no active project), tickets fall through to simplex_mind's own `database/tickets.db` under prefix `SIMP`.

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
python3 src/utils/agent_skills/tickets/ticket_list.py --query "campfire"  # duplicate check: LIKE over title+description, all statuses, no cap
python3 src/utils/agent_skills/tickets/ticket_list.py --all --limit 0     # full plain listing (default limit 50 prints a truncation banner)
```
List output is table-only; add `--json` for the machine-readable block.
```bash
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

## simplex CLI

The venv installs a `simplex` command (`pip install -e .`) fronting every brain tool —
`simplex doctor`, `simplex status`, `simplex ticket list`, `simplex memory search`,
`simplex history stats`, `simplex history purge`, `simplex backup`,
`simplex project use <name>` (a git-checkout wrapper); `simplex --help` lists the full
table. For agents without a hook system this CLI is the most convenient entry point. The
script paths in this file remain canonical and always work without the install.

---

## Conversation History Protocol

**Ingest** — runs via an **optional** cron job every 5 minutes (Linux/macOS) or the Windows Task Scheduler tasks from `scripts/setup_windows_tasks.ps1`; nothing installs either automatically — SETUP.md step 8 wires it up. (Claude Code additionally runs ingestion via a Stop hook in `.claude/settings.json` after every response — see CLAUDE.md; other agents rely on the scheduled job, and without one ingestion is manual.)
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

**Delete stored transcripts** (retention — see `PRIVACY.md`):
```bash
python3 src/utils/agent_skills/conversation/conversation_purge.py \
    --older-than 90 --dry-run    # preview; --yes to delete; message_usage preserved by default
```

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

This applies to the brain repo too: simplex_mind framework work (SIMP tickets) commits to
`develop` and merges to `master` only once verified working. `master` is what fresh machines
clone — it must always be stable.

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
- `database/config.json` — local onboarding/config state (committing it made fresh clones skip onboarding — SIMP-D2-021)
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
- `projects.yaml` and `database/config.json` are local config (gitignored). Never commit either. The active project is derived from the current simplex_mind git branch — to switch projects, just `git checkout <branch>` (or `simplex project use <name>`).
- Never assume the user is following along during multi-step execution. Present one step at a time, explain what success/failure looks like, and wait for confirmation before proceeding.
- Protocol changes land on `develop` and merge to `master` once verified; project branches then merge from `master` (ask the user which — see the post-pull guardrail below).
- `master` and `develop` are the only branches pushed online and both must stay project-free: never merge project branches into them, and never let project registrations (systems.md/MEMORY.md/config entries naming a project) land on them. Framework work reaches master by merging develop once verified. User-preference config lives outside the repo.
- **MANDATORY after every git pull that brings major changes into master:** immediately offer to update project branches, and ALWAYS ask the user which projects should receive the update (`git merge master` per selected branch). Never merge into project branches unprompted, and never skip the ask.

*(Add new guardrails as mistakes happen. Keep this under 15 items.)*

---

## File Structure — Where Things Live

```
simplex_mind/                          <- brain repo (agent launches here)
|-- CLAUDE.md                          <- Claude Code instructions
|-- AGENTS.md                          <- this file — Codex/Cursor/Windsurf instructions
|-- PRIVACY.md                         <- what is stored, where, how to remove it
|-- projects.yaml                      <- maps project names -> paths (local, gitignored)
|-- subconscious/                      <- reasoning-philosophy piece library (canonical, committed)
|-- pyproject.toml                     <- `simplex` CLI entry point, pytest/ruff config
|-- .github/workflows/ci.yml           <- CI: pytest + ruff, ubuntu + windows
|-- .claude/                           <- Claude Code only: settings.json hook registrations + subagent definitions (other agents: ignore)
|-- tests/                             <- pytest suite (hermetic; "a new tool needs a test")
|-- database/
|   |-- memory/
|   |   |-- memory.db                  <- structured memory (SQLite)
|   |   |-- MEMORY.md                  <- curated persistent memory
|   |   |-- systems.md                 <- system inventory
|   |   +-- logs/                      <- daily logs (YYYY-MM-DD.md)
|   |-- config.json                    <- local onboarding/config state (never committed)
|   |-- tickets.db                     <- brain (SIMP) tickets — each project has its own <project>/database/tickets.db
|   |-- conversation_history.db        <- conversation transcripts + token usage
|   |-- hooks.db                       <- hook session state + event log (runtime, gitignored; written by Claude Code hooks)
|   |-- backups/                       <- `simplex backup` snapshots (gitignored)
|   +-- ARCHITECTURE.md                <- database schema docs
|-- src/simplex_cli/                   <- installable `simplex` CLI (pip install -e .)
+-- src/utils/agent_skills/
    |-- memory/                        <- memory tools (hook_state.py -> hooks.db)
    |-- tickets/                       <- ticket tools (pretooluse_gate.py is a Claude Code hook)
    |-- conversation/                  <- conversation history tools (incl. conversation_purge)
    |-- subconscious/                  <- context-triggered philosophy: index, recall hook, miner, autotune
    |-- git_commit.py                  <- git operations
    |-- init.py                        <- project bootstrapper (--mark-onboarded)
    |-- doctor.py                      <- health checks, onboarding classification
    |-- backup_db.py                   <- SQLite online-backup of persistent DBs
    |-- project_resolver.py            <- branch -> project resolution, ticket DB routing
    |-- track_tokens.py                <- token metrics logger (optional)
    +-- manifest.md                    <- tool inventory
```

---

## Your Job in One Sentence

Load the session digest, read the active project's instructions, then be direct, reliable, and get things done.
