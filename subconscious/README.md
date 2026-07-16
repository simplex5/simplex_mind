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
source: <provenance note>
---

<prose body — the philosophy itself>
```

`name` is required. Note there are **no keywords in the piece files** — see below.

## Trigger keywords are personal — they never live in this repo

How a prompt is phrased is specific to one user; committing trigger phrases
would bake one person's speech patterns into everyone's setup. Keywords
therefore live in a local, gitignored overlay (like `projects.yaml`):

```
database/memory/subconscious_keywords.json
{"<piece-name>": ["trigger phrase", ...], ...}
```

The indexer merges the overlay at build time. Keywords match as word-prefixes
(single words) or normalized substrings (phrases); hyphens/underscores are
equivalent to spaces. A piece with no keywords still works — it matches on
embedding similarity alone (cosine ≥ 0.70), just less eagerly.

**Bootstrapping on a new machine/user:** run
`src/utils/agent_skills/subconscious/subconscious_mine.py` against that
machine's own conversation history, curate the report's suggestions into the
overlay file, and rebuild the index. Mining reports quote verbatim prompts —
keep them out of anything committed (`logs/` is gitignored).

**Migration note (pre-2026-07-16 setups):** keywords used to live in piece
frontmatter. If your index build warns about keyword-less pieces, recover your
old lists from git history (`git show <old-commit>:subconscious/<piece>.md`)
into your local overlay file, then rebuild.

## Growth loop

When a session produces a durable reasoning lesson — a failure worth preventing
or an approach worth repeating — write it as a new piece here, re-run the
indexer, and commit. The library is meant to accumulate.

Periodically run `subconscious_mine.py` against conversation history to surface
new trigger phrasings and candidate groups from real usage.
