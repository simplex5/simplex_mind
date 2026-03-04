# SETUP.md — Claude Code Agent Instructions

Paste the sections below into your project's `CLAUDE.md` to enable the full simplex_mind agent workflow. Alternatively, reference this file from your CLAUDE.md.

---
DO NOT PROCEED WITH INITIALIZING THE PROJECT WITHOUT DOING STEP 0 FIRST
READ THE EXISTING CLAUDE.md FILE BEFORE WELCOMING THE USER SO YOU KNOW THEIR PROJECT
DURING STEP 0 GUIDE THEM, BASED ON YOUR ANALYSIS OF THE EXISTING CLAUDE.md, ON HOW TO CHANGE THEIR CLAUDE.md

## Your Behavior

Do not assume the user is right. Think critically about every request. Keep descriptions short.

Before acting on any non-trivial request, restate your understanding of it in plain, everyday language — as if explaining to a friend who isn't a developer. Wait for confirmation before proceeding. This applies to feature requests, bug reports, architecture decisions, and refactors. Skip for simple questions or trivial one-liners.

---

## Onboarding

### Detection

At the start of every new session, check for `database/config.json`. If it contains `"onboarding_complete": true`, skip onboarding and proceed to normal session startup (load memory, list open tickets).

If `database/config.json` is missing or `onboarding_complete` is not `true`, run the onboarding flow below.

### New Project Flow

**Step 0 — Welcome**
Print a brief welcome message explaining what simplex_mind provides: persistent memory, ticket tracking, structured git commits, and a response summary protocol.

How should I integrate the simplex_mind agent protocol with your existing CLAUDE.md?
If the user selects integration discussion or append, ORGANIZE THE NEWLY GENERATED CLAUDE.md FILE IN THE REQUIRED HIERARCHY ORDER OF DECISIONS. DO NOT JUST APPEND THE SIMPLEX_MIND PROTOCOLS TO THE BOTTOM OF THEIR CLAUDE.md. MAKE INTELLIGENT DECISIONS ON THE ORDER SO THAT THE SIMPLEX_MIND SYSTEM STILL WORKS AND THEIR EXISTING PROJECT STILL WORKS. MAKE SURE THAT THE USER IS AWARE OF YOU DOING THIS AND EXPLICITLY TELL THEM.

  1. Integration discussion
     I'll walk through your CLAUDE_OG.md and we'll figure out together how to proceed.
  2. Append
     Add the agent protocol sections (memory, tickets, git, guardrails) to the end of the
     existing CLAUDE.md, keeping the MediaMTX docs intact.
  3. Replace
     Replace CLAUDE.md with the full simplex_mind template. The original MediaMTX content
     is safe in CLAUDE_OG.md.
  4. Blank user input (custom typable)



**Step 1 — Project basics**
Ask the user for:
- Project name
- One-line project description
- Tech stack (languages, frameworks, key libraries)

**Step 2 — Ticket prefix**
Ask the user for a ticket prefix: 3–5 uppercase letters (e.g., `CORN`, `FLUX`, `EGG`).
Validate: must be 3–5 characters, uppercase letters only. Re-prompt if invalid.

**Step 3 — Project goals**
Ask the user for their top 1–3 project goals (one sentence each).

**Step 4 — Existing code check**
If the project directory contains existing source code (beyond simplex_mind files), ask:
- (a) Auto-summarize the codebase into MEMORY.md
- (b) Learn as we go — skip for now
- (c) User will brief you manually

**Step 5 — Run init**
Run the initializer with the collected values:
```bash
python src/utils/agent_skills/init.py \
    --prefix <PREFIX> \
    --project-name "<name>" \
    --project-description "<description>" \
    --tech-stack "<stack>"
python src/utils/agent_skills/git_commit.py init
```

**Step 6 — Write goals/vision.md**
Create `goals/vision.md` containing:
- Project name
- Description
- Goals (from Step 3)
- Tech stack

**Step 7 — Seed MEMORY.md**
Update `database/memory/MEMORY.md` with project info:
- Project name and description
- Tech stack
- Ticket prefix
- Key directory structure (if auto-summarized in Step 4)

**Step 8 — Mark onboarding complete**
Write `"onboarding_complete": true` to `database/config.json` (merge with existing keys).

**Step 9 — Offer PRD creation**
Ask if the user wants to create a Product Requirements Doc (`goals/PRD.md`).

If yes, walk through sections one at a time. For each section, ask if the user wants to:
- Discuss and write it now
- Skip it and create a ticket to explore later

Sections:
1. Target Users
2. Core Features
3. User Stories
4. MVP Scope
5. Technical Architecture
6. Acceptance Criteria
7. Milestones
8. Constraints / Non-Goals
9. Risks

Skipped sections get a ticket (e.g., `"Explore: define acceptance criteria for MVP"`).

**Step 10 — Commit onboarding artifacts**
Stage and commit all files created during onboarding:
```bash
python src/utils/agent_skills/git_commit.py commit -m "onboarding: initialize project with simplex_mind"
```

### Existing Project (returning session)

If `database/config.json` exists with `"onboarding_complete": true`:
1. Load memory: `python src/utils/agent_skills/memory/memory_read.py --format markdown`
2. List open tickets: `python src/utils/agent_skills/tickets/ticket_list.py --status open`
3. Report count + any critical/high items
4. Proceed to normal conversation

### Integration Scenario

If simplex_mind files exist (e.g., `src/utils/agent_skills/`) but there is no `database/config.json`, AND the project already has its own content in `CLAUDE.md`:

Ask the user how to integrate:
- (a) Append the agent protocol sections to existing CLAUDE.md
- (b) Replace CLAUDE.md with the simplex_mind template
- (c) Keep them separate (user manages CLAUDE.md manually)

Then proceed with the new project onboarding flow from Step 1.

---

## Agent Protocol (paste into CLAUDE.md)

```markdown
## Agent Protocol

See [`AGENT_PROTOCOL.md`](AGENT_PROTOCOL.md) for the full specification. Key tools in `src/utils/agent_skills/`:

- **Memory**: `memory/memory_write.py`, `memory/memory_read.py`, `memory/hybrid_search.py` — SQLite-backed persistent memory with daily logs in `database/memory/`
- **Tickets**: `tickets/ticket_create.py`, `tickets/ticket_list.py`, `tickets/ticket_read.py`, `tickets/ticket_update.py` — JIRA-like issue tracking stored in `database/tickets.db`
- **Git**: `git_commit.py` — structured git commits with subcommands: `init`, `status`, `commit`, `diff`
- **Init**: `init.py` — bootstraps `database/` directory, SQLite schemas, and `MEMORY.md`

All scripts run with `python src/utils/agent_skills/...`.
```

---

## Response Summary (paste into CLAUDE.md)

```markdown
## Response Summary

After **every** response that makes changes, append a brief summary block:

---
**Git:** committed `<message>` / no commit — <reason>
**Ticket:** created <ID> / updated <ID> / no ticket — <reason>
**DB:** wrote memory / updated ticket db / no db write — <reason>
**Notes:** <anything else the user should know — warnings, deferred items, regressions caught, etc. Omit if nothing.>
**Commands:** `feature:` `bug:` `task:` `improvement:` `docs:` `question:`
Prefix your next message with the above. `feature:`, `improvement:`, `bug:`, and `question:` are self-explanatory. `task:` is work that doesn't fit those. `docs:` is for updating CLAUDE.md, manifests, etc.

Rules:
- Always include **Git** and **Ticket** lines, even when the answer is "nothing done".
- Valid "no commit" reasons: files outside git scope, benchmark run, no source changes.
- Valid "no ticket" reasons: pure conversation, already tracked, trivial one-liner.
- Always include **DB** line; valid "no db write" reasons: read-only task, pure conversation, no memory/ticket ops performed.
- **Notes** is optional — only include it if there is something actionable or surprising.
- Always include **Commands:** line as a persistent cheatsheet for input prefixes.
- Keep each line to one sentence. This is a status line, not a paragraph.
```

---

## Guardrails (paste into CLAUDE.md)

```markdown
## Guardrails — Learned Behaviors

- Always check `src/utils/manifest.md` before writing a new script
- Verification steps in plans must not require running scripts. Confirm changes
  by inspecting file contents and diffs only.
- When improving any file derived from a shared template or pattern, identify all sibling files of the same type.
  Confirm with the user before updating each sibling — apply only generalizable insights,
  not project-specific details.
- Before updating any project documentation file that is not the immediate subject
  of the current task, ask the user whether the update is wanted.
- Before any large refactor or rewrite, confirm the project's high-level goals
  and user-facing behaviors with the user. Implementation must preserve every
  observable behavior unless explicitly told otherwise.

*(Add new guardrails as mistakes happen. Keep this under 15 items.)*
```

---

## Git Branching Workflow (paste into CLAUDE.md)

```markdown
## Git Maintenance

### Branching Workflow

- **`main`** — Stable, production-quality code only. Never commit directly.
- **`develop`** — Integration branch. All feature/fix branches merge here first.
- **`release/<version>`** — Cut from `develop` when ready for release. Only bugfixes allowed on release branches. Merges into both `main` and `develop` when complete.
- **Feature/fix branches** — Branch from `develop`. Named `feature/<ticket-id>-<slug>` or `fix/<ticket-id>-<slug>`. One branch per ticket.

**Branching rules:**
- Never commit directly to `main` or `develop` — always use a branch + merge.
- Every branch name must reference a ticket ID (e.g., `feature/CORN-042-spinner-rework`).
- Before merging to `develop`: code must pass lint, tests (when applicable), and a self-review diff check.
- Tag `main` after each release merge with `v<major>.<minor>.<patch>`.
```

---

## Input Prefixes (paste into CLAUDE.md)

```markdown
## Input Prefixes

| Prefix | Ticket type | Use when… |
|--------|-------------|-----------|
| `feature:` | feature | Adding new capability |
| `bug:` | bug | Something is broken |
| `task:` | task | Work that doesn't fit above |
| `improvement:` | improvement | Enhancing something that works |
| `docs:` | documentation | Updating docs, CLAUDE.md, manifests |
| `question:` | — (none) | Just asking — no work tracked |
```
