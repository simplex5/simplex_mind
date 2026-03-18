# CLAUDE.md — simplex_mind Brain

## Your Behavior

Do not assume the user is right. Think critically about every request. Keep descriptions short.

For all questions you ask the user, immediately elaborate on the choices in layman's terms
so they understand clearly what you're suggesting.

When the user refers to something from a previous conversation that is not in your current
context, always search conversation history first. Do not search the repo and try to
recontextualize what they're asking. If the conversation history has no record of it,
treat that as a bug in the memory system — surface it to the user immediately rather than
compensating by figuring things out manually.

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
   Read `projects.yaml` in this repo root. Find the project with `active: true`.
   Expand `path` (e.g., `~/projects/cornucopia2`) and read `<path>/<ref_file>` (e.g., `CLAUDE.md.ref`).
   Follow the project-specific instructions in that file for the remainder of the session.

3. **Report readiness:**
   Report the open ticket count, any critical/high items, and confirm which project is active.

---

## Project Navigation

```yaml
# projects.yaml — maps project names to paths
projects:
  cornucopia2:
    path: ~/projects/cornucopia2
    ref_file: CLAUDE.md.ref
    active: true
```

- Only one project should have `active: true` at a time.
- To switch projects: set the current project to `active: false`, set the new one to `active: true`.
- To add a project: add an entry with `path`, `ref_file`, and `active: false`.

---

## Working Directory

simplex_mind is the launch directory, but most work happens in the active project.

- **Tickets, memory, conversation:** Always use simplex_mind's tools (centralized in this repo)
- **Git operations on project code:** Use native git commands in the project directory:
  ```bash
  cd ~/projects/cornucopia2  # or whatever projects.yaml says
  git add <files>
  git commit -m "type: description (CORN-NNN)"
  # Only when isolation is needed (see Branching Workflow):
  git checkout -b feature/CORN-NNN-slug
  ```
- **Git operations on simplex_mind itself:** Use `git_commit.py` (rare — only when editing brain tools)
- **File edits:** Use absolute paths to the project directory (from projects.yaml)

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

**Write with ticket cross-reference:**
```bash
python3 src/utils/agent_skills/memory/memory_write.py \
    --content "..." --type decision --ticket CORN-042
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
- Use Read + Edit tools on `database/memory/MEMORY.md`.
- Keep it under ~200 lines; content beyond that is truncated from context.
- Organise by topic, not chronologically. Remove outdated entries promptly.

**Systems inventory** (`database/memory/systems.md`):
- Registry of significant features and systems across all projects.
- Update when creating, removing, or significantly changing a system.
- Read by session_digest.py for the "Active Systems" section.

---

## Ticket Protocol

**Location:** `database/tickets.db`

**Commands:**
```bash
# Create
python3 src/utils/agent_skills/tickets/ticket_create.py \
    --type <bug|feature|task|improvement|documentation> \
    --title "Short summary" \
    --project <name> \
    --priority <low|medium|high|critical> \
    --description "Full details"

# Read / list
python3 src/utils/agent_skills/tickets/ticket_read.py --id CORN-001
python3 src/utils/agent_skills/tickets/ticket_list.py --status open
python3 src/utils/agent_skills/tickets/ticket_list.py --all

# Update
python3 src/utils/agent_skills/tickets/ticket_update.py \
    --id CORN-001 --status <open|in_progress|blocked|done|wont_fix>
python3 src/utils/agent_skills/tickets/ticket_update.py \
    --id CORN-001 --priority high --note "Context note"
```

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

- **Start**: run `ticket_list.py --status open`, report count + critical/high items.
- **During work**: create tickets as issues surface — do not batch at the end.
- **End**: summarise tickets created this session by ID and title.

---

## Conversation History Protocol

**Ingest** (runs automatically via cron every 5 minutes):
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
**Branch:** on `develop` / created `feature/CORN-NNN`
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
python3 src/utils/agent_skills/git_commit.py status
python3 src/utils/agent_skills/git_commit.py diff
python3 src/utils/agent_skills/git_commit.py commit -m "message"
```

These commands operate on **simplex_mind's own repo**. For project repos (e.g., cornucopia2),
use native git commands in the project directory — see [Working Directory](#working-directory).

**Commit automatically after:**
- Running `init.py` for the first time
- Writing or updating any file in `src/`
- Modifying `CLAUDE.md`, `AGENTS.md`, `projects.yaml`, or `database/memory/MEMORY.md`

**Never commit after:**
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

*(Add new guardrails as mistakes happen. Keep this under 15 items.)*

---

## File Structure — Where Things Live

```
simplex_mind/                          ← brain repo (Claude launches here)
├── CLAUDE.md                          ← this file — agnostic base instructions
├── AGENTS.md                          ← Codex/Cursor/Windsurf instructions
├── projects.yaml                      ← maps project names → paths
├── database/
│   ├── memory/
│   │   ├── memory.db                  ← structured memory (SQLite)
│   │   ├── activity.db                ← audit trail
│   │   ├── MEMORY.md                  ← curated persistent memory
│   │   ├── systems.md                 ← system inventory
│   │   └── logs/                      ← daily logs (YYYY-MM-DD.md)
│   ├── tickets.db                     ← ticket tracking
│   ├── conversation_history.db        ← conversation transcripts
│   └── ARCHITECTURE.md                ← database schema docs
└── src/utils/agent_skills/
    ├── memory/                        ← memory tools
    ├── tickets/                       ← ticket tools
    ├── conversation/                  ← conversation history tools
    ├── git_commit.py                  ← git operations
    ├── init.py                        ← project bootstrapper
    └── manifest.md                    ← tool inventory
```

---

## Your Job in One Sentence

Load the session digest, read the active project's instructions, then be direct, reliable, and get things done.
