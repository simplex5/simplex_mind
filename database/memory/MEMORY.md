# Persistent Memory

> This file contains curated long-term facts, preferences, and context that persist across sessions.
> The AI reads this at the start of each session. You can edit this file directly.

## Orchestrator Insights

## Model Behaviors

## Key Facts

- Framework: GOTCHA (Goals, Orchestration, Tools, Context, Hardprompts, Args)
- PRD location: goals/projects/<name>/PRD.md (configurable via --prd flag)
- Primary metric: claude_token_ratio = claude_tokens / all_agents_tokens (target < 0.70)

## Learned Behaviors

- Always check src/utils/manifest.md before creating new scripts
- Follow GOTCHA framework: Goals, Orchestration, Tools, Context, Hardprompts, Args
- Review prompts are project-agnostic (loaded from src/context/hardprompts/)

## Git Integration

- Policy: goals/git.md — commit after framework changes, never after benchmark runs
- Tool: src/utils/claude_code_skills/git_commit.py — subcommands: init, status, commit, diff

## Current Configuration

- Review prompt: src/context/hardprompts/review_prompt.txt
- Fix prompt: src/context/hardprompts/fix_prompt.txt
- Config: args/orchestrator.yaml

---

*Last updated: (date)*
*This file is the source of truth for persistent facts. Edit directly to update.*
