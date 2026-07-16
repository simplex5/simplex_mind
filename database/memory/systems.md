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
need `--scan-all` — the ComfyUI transcripts were rescued this way.

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

---

## Retired Systems

*No systems retired yet.*
