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

### Step 4 — Set up conversation history (optional, Claude Code only)

```
crontab -e
# Add (adjust path if simplex_mind is not at ~/projects/simplex_mind):
*/5 * * * * ~/projects/simplex_mind/venv/bin/python \
  ~/projects/simplex_mind/src/utils/agent_skills/conversation/conversation_ingest.py \
  >> ~/projects/simplex_mind/logs/conversation_ingest.log 2>&1
```

### Optional: Semantic memory search

For vector-based memory search (requires an OpenAI API key):

```
pip install openai rank_bm25
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### Notes

- Use `python3` (not `python`) to run all agent scripts
- simplex_mind sits alongside your project repos as a sibling — it does not go inside them
- Both CLAUDE.md and AGENTS.md can coexist; they reference the same tooling
