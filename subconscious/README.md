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
  - <trigger phrase>
  - <trigger phrase>
source: <provenance note>
---

<prose body — the philosophy itself>
```

`name` and `keywords` are required. Keywords match as word-prefixes (single
words) or normalized substrings (phrases); hyphens/underscores are equivalent
to spaces.

## Growth loop

When a session produces a durable reasoning lesson — a failure worth preventing
or an approach worth repeating — write it as a new piece here, re-run the
indexer, and commit. The library is meant to accumulate.

Periodically run `subconscious_mine.py` against conversation history to surface
new trigger phrasings and candidate groups from real usage.
