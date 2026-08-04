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
implementer/verifier from sonnet to opus. Current pins (synced to frontmatter
2026-08-04): gameplay-implementer (opus/xhigh, codes to spec, never commits),
code-reviewer (opus/xhigh, read-only diff review), playtest-verifier (opus/xhigh,
engine-side verification with evidence, never saves mutated scenes), scribe
(sonnet/xhigh, tickets/memory/checklists via the CLI tools), game-designer (opus/xhigh,
read-only design proposals), researcher (opus/high, sourced lookups). All project-agnostic per the framework guardrail; the
orchestrator retains git and ticket authority. Replaced the removed `/agents` wizard
workflow.

**Protocol enforcement layer** (SIMP-D2-017, 2026-07-26): hooks enforce what instructions
couldn't. SessionStart hook auto-injects `session_digest.py` (start protocol can no longer be
skipped); `memory/protocol_gate.py` on UserPromptSubmit machine-counts the 5-ticket memory
cadence (`tickets.resolved_at` vs `MAX(memory_entries.created_at)`), re-surfaces pending
autotune candidates mid-session, and detects harness-auto-memory-instead-of-memory.db
substitution. Read-only DBs, throttled (cadence nag ≤ every 10 prompts, others once/session),
always fail-open. Born from the 2026-07-26 breakdown: a ~5-hour session wrote zero memory.db
entries while following the ticket protocol perfectly — response-shaped instructions fire,
condition-shaped ones don't. CLAUDE.md carries the matching routing rules (two memory systems,
reports are outputs never state, instruction precedence, wrap-up trigger replacing the
unreachable "End" cadence). Extended 2026-07-27 (SIMP-D2-022): digest sections render broken
subsystems as `UNAVAILABLE — <reason>` instead of healthy emptiness, gate checks that raise
surface a once-per-session `[protocol-gate degraded: ...]` marker, and the cadence query is
scoped to `project:<name>` tags (memory_write auto-tags; global fallback until first tagged
write per project). Extended 2026-07-29 (Hermes reports batch, SIMP-D2-038/039): hook session
state moved from leaked temp-dir JSON into `database/hooks.db` via `memory/hook_state.py`
(WAL, fail-open, 90-day event retention) — `hook_events` logs every check outcome + invocation
duration, the measurement substrate for warn→deny decisions and hook-latency questions; doctor
gained a hook-events section. New `tickets/pretooluse_gate.py` PreToolUse hook enforces the
last prose-only hard rule: warn-once `[ticket-gate]` demand when an Edit/Write/NotebookEdit
call starts with no open/in_progress ticket in the routed DB (unmanaged paths skipped; v1
never denies and never emits a permissionDecision). Memory recall became project-scoped the
same day (SIMP-D2-037): `scope` + `provenance` columns, shared `scope_predicate()` (active +
unexpired + project-or-global) on every read path, `--all-projects` to widen.

**simplex CLI + doctor + CI** (SIMP-D2-021/023/025/026/027, 2026-07-27 — born from an external
GPT 5.6 review of a friend's failed fresh-clone install): `pip install -e .` installs the
`simplex` command (`src/simplex_cli/cli.py`, thin dispatcher over the agent-skills tools —
script paths stay canonical for hooks/cron/other agents). Subcommands: init, doctor, status,
digest, ticket/memory/history tools, `history purge` (transcript retention/deletion, preserves
`message_usage` by default, see PRIVACY.md), `backup` (SQLite online-backup of all DBs to
gitignored `database/backups/<UTC>/`), `project use <name>` (= git checkout of the project's
branch). `doctor.py` runs 13 health checks with per-check remediation, exit 1 when degraded;
`classify_onboarding` distinguishes fresh_clone from lost_config — the seam created by
untracking `database/config.json` (the root-cause bug: a committed
`onboarding_complete: true` made every fresh clone skip SETUP.md onboarding). Established
machines pulling the untrack commit lose their config.json; digest + doctor print the repair
(`init.py --mark-onboarded`). CI (`.github/workflows/ci.yml`): pytest + ruff on
ubuntu/windows × py3.10/3.12, plus a live bare-checkout doctor assertion (must exit nonzero
and say "fresh clone"). Deferred: full bootstrap state machine (SIMP-D2-028, do not start
without user).

---

## Retired Systems

*No systems retired yet.*
