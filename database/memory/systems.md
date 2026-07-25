# System Inventory

> Registry of significant features and systems across all projects.
> Update when creating, removing, or significantly changing a system.

---

## Active Systems

### simplex_mind brain (prefix SIMP)
**Conversation history preservation** (`src/utils/agent_skills/conversation/`): Stop hook +
5-min cron ingest Claude Code JSONL transcripts into `database/conversation_history.db`
(sessions/messages/FTS) before the ~30-day transcript cleanup deletes them. Incremental via
per-file byte offsets; dedup by message uuid. **Token accounting (SIMP-040):** `message_usage`
table captures per-response API token counts (input/output/cache write/cache read, model) for
every assistant response — including tool-call-only responses that carry usage but no text and
never reach `messages`. Backfilled 2026-07-15 (6,893 responses, 1.37B tokens, coverage from
2026-06-03; older usage unrecoverable — source files already cleaned). Totals + per-month
breakdown in `conversation_read.py --action stats`. Caveat: default source dirs derive from
`projects.yaml` paths; sessions launched from unregistered subdirs (e.g. ~/projects/comfy/ComfyUI)
need `--scan-all` — the ComfyUI transcripts were rescued this way. **Windows (SIMP-D1-052,
SIMP-D2-002):** framework runs on native Windows + Git Bash; transcript dirs are discovered by
matching the JSONL `cwd` field (Windows slug encoding is undocumented), hooks auto-select `py`
vs `python3` via uname, settings.json forces PYTHONUTF8=1 (cp1252 mojibake fix).
`scripts/setup_windows_tasks.ps1` registers Task Scheduler mirrors of the cron jobs
(SimplexMind-Ingest 5-min safety net, SimplexMind-Autotune Sun 4am; venv pythonw, per-user).
Onboarding: SETUP-WINDOWS.md.

**Subconscious** (`src/utils/agent_skills/subconscious/` + `subconscious/` library): context-
triggered reasoning-philosophy injection. Piece library (markdown, no keywords) lives
canonically in the repo root `subconscious/` directory — migrated in-repo 2026-07-16
(SIMP-L1-019); the projects.yaml `subconscious:` key and `get_subconscious_source()` were
removed. Trigger keywords are two layers (SIMP-D1-045/046, 2026-07-16): generic defaults in
piece frontmatter (committed — works out of the box) + personal phrasing in the local
gitignored overlay `database/memory/subconscious_keywords.json`, merged at index build and
tuned by mining one's own conversation history. Indexer embeds pieces + merged keywords
into `database/memory/subconscious_index.json` (derived, gitignored — rebuild once per
machine and after piece/keyword edits); `subconscious_recall.py` runs as a UserPromptSubmit
hook, injects ≤2 matching pieces once per session, fails open. Weekly autotune cron
(`subconscious_autotune.py`, Sun 4am, SIMP-D1-047): mines gated keyword candidates into a
pending queue surfaced by session_digest; applied only after in-session user approval.

**Subagent roster** (`.claude/agents/`, SIMP-D2-006, 2026-07-20; effort tiers added
SIMP-D2-008, 2026-07-22; retiered for Opus 5 SIMP-D2-009, 2026-07-25): six generic
game-dev subagent definitions with per-agent model+effort pins, set once in frontmatter
and NOT tied to whatever model the orchestrating session happens to be running — the pins
stay fixed even if the orchestrator later runs a cheaper/pricier model itself. Opus 5's
release (same $5/$25 price as Opus 4.8, stronger agentic coding, review accurate at lower
effort; `model: opus` is an alias so opus pins auto-resolve to it) motivated promoting
implementer/verifier from sonnet to opus and lowering reviewer effort. gameplay-implementer
(opus/xhigh, codes to spec, never commits), code-reviewer (opus/medium, read-only diff
review), playtest-verifier (opus/xhigh, engine-side verification with evidence, never
saves mutated scenes), scribe (haiku, no effort pin, tickets/memory/checklists via the
CLI tools), game-designer (opus/high, read-only design proposals), researcher (haiku, no
effort pin, sourced lookups). All project-agnostic per the framework guardrail; the
orchestrator retains git and ticket authority. Replaced the removed `/agents` wizard
workflow.

---

## Retired Systems

*No systems retired yet.*
