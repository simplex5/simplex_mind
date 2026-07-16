# Subconscious Library

Reasoning-philosophy "pieces" injected into context automatically when a user
prompt matches — philosophy costs context only when relevant. This directory is
the canonical library; it ships with the brain repo so the feature works on any
machine after one index rebuild.

## How it flows

1. Pieces live here as `*.md` files (see format below).
2. The indexer embeds them into a self-contained index:
   ```bash
   python3 src/utils/agent_skills/subconscious/subconscious_index.py
   ```
   → writes `database/memory/subconscious_index.json` (gitignored, machine-local).
3. A `UserPromptSubmit` hook (`subconscious_recall.py`) matches each prompt
   against the index (keywords primary, embedding cosine ≥ 0.70 as rescue) and
   injects at most 2 pieces, each at most once per session. Always fails open.

## Piece format

```markdown
---
name: <slug>
summary: <one line>
keywords:
  - <generic trigger phrase>
source: <provenance note>
---

<prose body — the philosophy itself>
```

`name` is required; `keywords` is the generic default layer — see below.

## Keywords are two layers: generic defaults here, personal phrasing local

- **Frontmatter `keywords:` (committed)** — generic starter triggers anyone
  would say ("verify", "double check", "root cause"). They make the feature
  work at a basic level on any fresh machine, out of the box. Keep them
  universal: one person's speech patterns do not belong in this repo.
- **Local overlay (gitignored, like `projects.yaml`)** — personal phrasing
  mined from one user's own history, merged on top at index build:

  ```
  database/memory/subconscious_keywords.json
  {"<piece-name>": ["trigger phrase", ...], ...}
  ```

Keywords match as word-prefixes (single words) or normalized substrings
(phrases); hyphens/underscores are equivalent to spaces. A piece with no
keywords at all still works — it matches on embedding similarity alone
(cosine ≥ 0.70), just less eagerly.

**Tuning to a new machine/user:** run
`src/utils/agent_skills/subconscious/subconscious_mine.py` against that
machine's own conversation history, curate the report's suggestions into the
local overlay, and rebuild the index. Mining reports quote verbatim prompts —
keep them out of anything committed (`logs/` is gitignored).

## Growth loop

When a session produces a durable reasoning lesson — a failure worth preventing
or an approach worth repeating — write it as a new piece here, re-run the
indexer, and commit. The library is meant to accumulate.

Periodically run `subconscious_mine.py` against conversation history to surface
new trigger phrasings and candidate groups from real usage.
