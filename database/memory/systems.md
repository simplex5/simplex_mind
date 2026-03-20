# System Inventory

> Registry of significant features and systems in the GOTCHA framework.
> Update when creating, removing, or significantly changing a system.

---

## Active Systems

### Orchestrator Pipeline
- **Location:** `src/utils/agent_skills/orchestrator.py`
- **Purpose:** Benchmark driver that reads PRD, dispatches code generation to LM Studio and review/fix to Gemini, logs token metrics
- **Key files:** orchestrator.py, dispatcher.py, workflow.py, prd_parser.py, track_tokens.py
- **Added:** initial

### Workflow Engine
- **Location:** `src/utils/run_loop/workflow.py`
- **Purpose:** Per-file generate-review-fix loop; loads LLM skills, gates on linter, injects lint errors and failure patterns into prompts
- **Key files:** workflow.py, dispatcher.py, linter.py, writer.py
- **Added:** initial (enhanced by CORN-076, CORN-078, CORN-082)

### User Review Pipeline (Feedback)
- **Location:** `src/utils/run_loop/user_review.py`
- **Purpose:** Multi-stage feedback loop: triage, plan (search/replace), apply, diff, review, fix
- **Key files:** user_review.py, dispatcher.py, writer.py, term.py
- **Added:** CORN-067

### Clarify Feedback Loop
- **Location:** `src/utils/run_loop/clarify_feedback.py`
- **Purpose:** Interactive Q&A that clarifies vague user feedback before passing to the review pipeline
- **Key files:** clarify_feedback.py, dispatcher.py, user_review.py
- **Added:** CORN-079 (enhanced by CORN-080)

### Unified Model Dispatcher
- **Location:** `src/utils/run_loop/dispatcher.py`
- **Purpose:** Routes prompts to LM Studio, Gemini, OpenAI, or Anthropic via CLI spec strings
- **Key files:** dispatcher.py, lmstudio.py, gemini.py, openai_client.py, anthropic_client.py
- **Added:** initial (extended by CORN-050, CORN-057)

### Deterministic File Linter
- **Location:** `src/utils/run_loop/linter.py`
- **Purpose:** Extension-based syntax linting (JS via node --check, HTML via html.parser, CSS via brace check); gates workflow on errors
- **Key files:** linter.py, workflow.py
- **Added:** CORN-076

### Memory System
- **Location:** `src/utils/agent_skills/memory/memory_db.py`
- **Purpose:** SQLite CRUD with hybrid search (BM25 + vector) for persistent cross-session knowledge
- **Key files:** memory_db.py, memory_read.py, memory_write.py, memory_post_run.py, hybrid_search.py, semantic_search.py, embed_memory.py
- **Added:** initial

### Ticket System
- **Location:** `src/utils/agent_skills/tickets/ticket_db.py`
- **Purpose:** Per-project SQLite CRUD for JIRA-like ticket tracking; each project has its own `<project_path>/database/tickets.db` with project-specific prefix (CORN, SHOP, SIMP); routing via `project_resolver.py`
- **Key files:** ticket_db.py, ticket_create.py, ticket_update.py, ticket_list.py, ticket_read.py, project_resolver.py
- **Added:** initial (refactored to per-project DBs by SHOP-123)

### Debug Methodology
- **Location:** `src/utils/agent_skills/debug/`
- **Purpose:** Markdown process guides for triaging failures; generic template + project-specific failure pattern tables
- **Key files:** debug_template.md, asteroids/debug.md, snake/debug.md, vampire_survivors/debug.md, oimemusic/debug.md
- **Added:** initial (enhanced by CORN-082)

### LLM Skills Library
- **Location:** `src/utils/LLM_skills/`
- **Purpose:** Reusable design-system standards (markdown) injected into prompts per file via PRD skills field
- **Key files:** all_skills/*.md, per-project copies in project dirs
- **Added:** initial

### PRD Parser
- **Location:** `src/utils/run_loop/prd_parser.py`
- **Purpose:** Parses PRD.md into FileSpec objects (description, skills, prompt, checklist per file)
- **Key files:** prd_parser.py, orchestrator.py
- **Added:** initial

### Token Tracker
- **Location:** `src/utils/agent_skills/track_tokens.py`
- **Purpose:** Appends LLM call objects to metrics JSON for token accounting and cost analysis
- **Key files:** track_tokens.py, orchestrator.py, csv_export.py
- **Added:** initial

### CSV Metrics Exporter
- **Location:** `src/utils/run_loop/csv_export.py`
- **Purpose:** Aggregates metrics JSON from all benchmark runs into a single analysis CSV
- **Key files:** csv_export.py, orchestrator.py
- **Added:** initial

### Memory Post-Run Automation
- **Location:** `src/utils/agent_skills/memory/memory_post_run.py`
- **Purpose:** Auto-called after each run; writes run insight, creates bug tickets for high fix-cycle files, upserts model-performance facts
- **Key files:** memory_post_run.py, memory_db.py, ticket_db.py
- **Added:** initial

### Conversation History
- **Location:** `src/utils/agent_skills/conversation/`
- **Purpose:** Verbatim conversation transcript storage from Claude Code JSONL files; cron-ingested every 5 min; FTS5 search, session browsing
- **Key files:** conversation_db.py, conversation_ingest.py, conversation_read.py
- **Added:** CORN-087

### Git Operations
- **Location:** `src/utils/agent_skills/git_commit.py`
- **Purpose:** Init, status, commit, diff for framework files
- **Key files:** git_commit.py, init.py
- **Added:** initial

### Shop Smart (app_test2)
- **Location:** ~/projects/app_test2
- **Purpose:** React Native + Expo grocery shopping optimization app — OCR receipt scanning, multi-store price comparison, payment method optimization
- **Key files:** App.tsx, src/context/*.js, screens/*.js, PRD.md, CLAUDE.md.ref
- **Added:** SHOP-118

---

## Retired Systems

*No systems retired yet.*
