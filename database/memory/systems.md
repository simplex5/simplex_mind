# System Inventory

> Registry of significant features and systems across all projects.
> Update when creating, removing, or significantly changing a system.

---

## Active Systems

*No systems registered yet. Systems will be added as you build.*

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

---

## Retired Systems

*No systems retired yet.*
