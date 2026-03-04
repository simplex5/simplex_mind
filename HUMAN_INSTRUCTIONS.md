## Setup Instructions

### Step 1 — Back up your existing files

Rename your existing project files before copying simplex_mind files over:

```
CLAUDE.md   → CLAUDE_OG.md
README.md   → README_OG.md
SETUP.md    → SETUP_OG.md
```

### Step 2 — Copy simplex_mind files

```
src/              (merge contents into your existing src/ if you have one)
AGENT_PROTOCOL.md
AGENTS.md
CLAUDE.md
README.md
SETUP.md
```

### Step 3 — Run onboarding

#### Claude Code users

```bash
# Open Claude Code (do NOT run /init)
# Enter plan mode: /plan
# Type: initialize
```

It will guide you through integration and put your existing files back.

#### Codex / Cursor / Windsurf / GitHub Copilot Workspace users

Open the assistant with `AGENTS.md` loaded (it should be picked up automatically from the repo root).
Then type:

```
initialize
```

The onboarding flow in `SETUP.md` applies to both Claude and Codex — follow the prompts.

---

**Notes:**
- Use `python3` (not `python`) to run all agent scripts.
- If you're concerned about file integrity, back up files before copying — in plan mode the assistant must show you diffs before making changes.
- Both `CLAUDE.md` and `AGENTS.md` can coexist; they reference the same tooling in `src/utils/agent_skills/`.
