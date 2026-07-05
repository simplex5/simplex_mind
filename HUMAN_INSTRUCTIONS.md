## Setup Instructions

### Prerequisites

- Python 3.10+
- Git
- An AI coding assistant (Claude Code, Codex, Cursor, Windsurf, or similar)

### Step 1 — Clone simplex_mind

Clone this repo alongside your project repos (not inside them):

```
cd ~/projects          # or wherever you keep repos
git clone <repo-url> simplex_mind
```

### Step 2 — Create the virtual environment

```
cd simplex_mind
python3 -m venv venv
source venv/bin/activate   # or: venv/bin/activate.fish
pip install -r requirements.txt
```

### Step 3 — Run onboarding

Open your AI assistant in the simplex_mind directory. It will detect that onboarding
hasn't been completed and guide you through setup:

- Claude Code: open Claude Code in `~/projects/simplex_mind`, then type `initialize`
- Codex / Cursor / Windsurf: open with AGENTS.md loaded, then type `initialize`

The onboarding will ask for your project path, name, ticket prefix, and goals.

### Step 4 — Conversation history (Claude Code: automatic)

For Claude Code, conversation ingestion runs automatically via a Stop hook in
`.claude/settings.json` after every response — nothing to set up.

Optionally add a cron job as a safety net (covers crashed sessions and non-Claude agents):

```
crontab -e
# Add (adjust path if simplex_mind is not at ~/projects/simplex_mind):
*/5 * * * * ~/projects/simplex_mind/venv/bin/python \
  ~/projects/simplex_mind/src/utils/agent_skills/conversation/conversation_ingest.py \
  >> ~/projects/simplex_mind/logs/conversation_ingest.log 2>&1
```

### Semantic memory search (works out of the box)

Semantic search runs fully locally via `fastembed`, which Step 2 already installed from
`requirements.txt` — no API key, no extra setup.

Troubleshooting: if memory search reports `keyword_only (semantic backend unavailable)`,
fastembed didn't install into the venv — re-run `pip install -r requirements.txt` with the
venv activated.

Optional OpenAI fallback instead of the local model:

```
pip install openai
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### Notes

- Use `python3` (not `python`) to run all agent scripts
- simplex_mind sits alongside your project repos as a sibling — it does not go inside them
- Both CLAUDE.md and AGENTS.md can coexist; they reference the same tooling
