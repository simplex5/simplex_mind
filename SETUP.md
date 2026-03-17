# SETUP.md — simplex_mind Onboarding

simplex_mind is the **brain repo** that sits alongside your project repos. It provides persistent memory, ticket tracking, conversation history, and a response summary protocol.

---

DO NOT PROCEED WITH INITIALIZING THE PROJECT WITHOUT DOING STEP 0 FIRST
READ THE EXISTING CLAUDE.md or AGENTS.md FILE BEFORE WELCOMING THE USER SO YOU KNOW THEIR PROJECT
DURING STEP 0 GUIDE THEM, BASED ON YOUR ANALYSIS OF THE EXISTING CLAUDE.md or AGENTS.md, ON HOW TO CHANGE THEIR CLAUDE.md or AGENTS.md

## Your Behavior

Do not assume the user is right. Think critically about every request. Keep descriptions short.

Before acting on any non-trivial request, restate your understanding in plain language. Wait for confirmation before proceeding.

---

## Onboarding

### Detection

At the start of every new session, check for `database/config.json`. If it contains `"onboarding_complete": true`, skip onboarding and proceed to normal session startup:

1. Run session digest: `python3 src/utils/agent_skills/memory/session_digest.py`
2. Read `projects.yaml` to find the active project
3. Read the active project's `CLAUDE.md.ref` (at `<path>/<ref_file>`)
4. Report open ticket count + critical/high items
5. Proceed to normal conversation

If `database/config.json` is missing or `onboarding_complete` is not `true`, run the onboarding flow below.

### New Project Flow

**Step 0 — Welcome & Project Path**
Print a brief welcome. Ask for:
- Path to the project repo (e.g., `~/projects/my-project`)
- Create a `projects.yaml` entry for it

How should I integrate the simplex_mind agent protocol with your existing CLAUDE.md or AGENTS.md?
  1. Integration discussion — walk through together
  2. Append — add agent protocol sections to existing file
  3. Replace — use simplex_mind template (original saved as backup)
  4. Custom

**Step 1 — Project basics**
Ask the user for:
- Project name
- One-line project description
- Tech stack (languages, frameworks, key libraries)

**Step 2 — Ticket prefix**
Ask for a ticket prefix: 3–5 uppercase letters (e.g., `CORN`, `FLUX`, `EGG`).
Validate: must be 3–5 characters, uppercase letters only.

**Step 3 — Project goals**
Ask for top 1–3 project goals (one sentence each).

**Step 4 — Existing code check**
If the project directory has existing source code:
- (a) Auto-summarize the codebase into MEMORY.md
- (b) Learn as we go — skip for now
- (c) User will brief you manually

**Step 5 — Run init**
```bash
python3 src/utils/agent_skills/init.py \
    --prefix <PREFIX> \
    --project-name "<name>" \
    --project-description "<description>" \
    --tech-stack "<stack>"
python3 src/utils/agent_skills/git_commit.py init
```

**Step 6 — Write goals/vision.md**
Create `goals/vision.md` in the project repo containing project name, description, goals, tech stack.

**Step 7 — Seed MEMORY.md**
Update `database/memory/MEMORY.md` with project info.

**Step 8 — Mark onboarding complete**
Write `"onboarding_complete": true` to `database/config.json`.

**Step 9 — Set up cron** (conversation history auto-ingestion)
```bash
crontab -e
# Add:
*/5 * * * * ~/projects/simplex_mind/venv/bin/python \
  ~/projects/simplex_mind/src/utils/agent_skills/conversation/conversation_ingest.py \
  >> ~/projects/simplex_mind/logs/conversation_ingest.log 2>&1
```

**Step 10 — Create project CLAUDE.md.ref**
Create `CLAUDE.md.ref` in the project root with project-specific instructions. Register it in `projects.yaml`.

**Step 11 — Commit onboarding artifacts**
```bash
python3 src/utils/agent_skills/git_commit.py commit -m "onboarding: initialize project with simplex_mind"
```

---

## Python Virtual Environment

```bash
cd ~/projects/simplex_mind
python3 -m venv venv
source venv/bin/activate
pip install python-dotenv
# Optional: pip install openai numpy rank_bm25
```

---

## Agent Protocol (paste into CLAUDE.md or AGENTS.md)

```markdown
## Agent Protocol

See [`AGENT_PROTOCOL.md`](AGENT_PROTOCOL.md) for the full specification. Key tools in `src/utils/agent_skills/`:

- **Memory**: `memory/memory_write.py`, `memory/memory_read.py`, `memory/hybrid_search.py`, `memory/memory_sync.py`, `memory/session_digest.py`
- **Tickets**: `tickets/ticket_create.py`, `tickets/ticket_list.py`, `tickets/ticket_read.py`, `tickets/ticket_update.py`
- **Conversation**: `conversation/conversation_ingest.py`, `conversation/conversation_read.py`
- **Git**: `git_commit.py` — `init`, `status`, `commit`, `diff`
- **Init**: `init.py` — bootstraps `database/` directory, SQLite schemas, and `MEMORY.md`
```

---

## Response Summary (paste into CLAUDE.md or AGENTS.md)

```markdown
## Response Summary

After **every** response that makes changes, append:

---
**Git:** committed `<message>` / no commit — <reason>
**Ticket:** created <ID> / updated <ID> / no ticket — <reason>
**DB:** wrote memory / updated ticket db / no db write — <reason>
**Notes:** <warnings, deferred items — omit if nothing>
**Commands:** `feature:` `bug:` `task:` `improvement:` `docs:` `question:`
```

---

## Guardrails (paste into CLAUDE.md or AGENTS.md)

```markdown
## Guardrails — Learned Behaviors

- Always check `src/utils/agent_skills/manifest.md` before writing a new script
- Always branch from the current working branch, not from develop, unless already on develop
- Create a ticket and feature branch before any file edits
- Verification steps in plans must not require running scripts
- Before updating any documentation file not the immediate subject of the task, ask the user
- Update `database/memory/systems.md` when creating, removing, or significantly changing a system

*(Add new guardrails as mistakes happen. Keep this under 15 items.)*
```

---

## Git Branching Workflow (paste into CLAUDE.md or AGENTS.md)

```markdown
## Git Maintenance

### Branching Workflow

- **`main`** / **`master`** — Stable. Never commit directly.
- **`develop`** — Integration branch. Feature/fix branches merge here first.
- **Feature/fix branches** — Branch from current working branch. Named `feature/<ticket-id>-<slug>` or `fix/<ticket-id>-<slug>`.

**Rules:**
- Never commit directly to main or develop
- Every branch name must reference a ticket ID
- Before merging to develop: pass lint and self-review diff check
```

---

## Input Prefixes (paste into CLAUDE.md or AGENTS.md)

```markdown
## Input Prefixes

| Prefix | Ticket type | Use when... |
|--------|-------------|-------------|
| `feature:` | feature | Adding new capability |
| `bug:` | bug | Something is broken |
| `task:` | task | Work that doesn't fit above |
| `improvement:` | improvement | Enhancing something that works |
| `docs:` | documentation | Updating docs, manifests |
| `question:` | — (none) | Just asking — no work tracked |
```
