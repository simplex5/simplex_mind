# Getting Started (for humans)

**simplex_mind is a brain repo for AI coding agents** — it gives them persistent memory,
ticket tracking, conversation history that survives transcript cleanup, and a consistent
commit/reporting protocol. It sits **alongside** your project repos as a sibling, never inside
them, and one brain serves all your projects.

This page is the quick start. See [README.md](README.md) for what it does and how it's
structured, and [SETUP.md](SETUP.md) for the onboarding flow your agent follows.

> ### On Windows? Read this first.
> **Install [Git for Windows](https://gitforwindows.org/) and use Git Bash as your shell.**
> This is required, not a preference — it is what provides the bash environment the whole
> system assumes:
>
> - The hooks in `.claude/settings.json` declare `bash` as their shell and detect Windows by
>   matching `uname -s` against `MINGW*`/`MSYS*`/`CYGWIN*`. Without Git Bash they **cannot run
>   at all**, which silently disables conversation-history ingest and subconscious recall in
>   Claude Code. Nothing errors — the features just never fire.
> - Every command in these docs is bash syntax. `source venv/Scripts/activate` has no cmd or
>   PowerShell equivalent, so **any** agent (Codex, Cursor, Windsurf included) needs Git Bash
>   to follow them.
>
> The commands below are otherwise written for Linux/macOS and **will fail on native Windows** —
> the venv layout and Python launcher differ. Follow
> [SETUP-WINDOWS.md](SETUP-WINDOWS.md) instead: `py` instead of `python3`,
> `venv/Scripts/activate` instead of `venv/bin/activate`, and Task Scheduler
> (`scripts/setup_windows_tasks.ps1`) instead of the cron job in Step 4.

---

## Prerequisites

- Python 3.10+
- Git — **on Windows this must be [Git for Windows](https://gitforwindows.org/)**, and you
  should work in Git Bash (see the callout above for why)
- An AI coding assistant (Claude Code, Codex, Cursor, Windsurf, or similar)

## Step 1 — Clone simplex_mind

Clone it **next to** your project repos, not inside one:

```bash
cd ~/projects          # or wherever you keep repos
git clone <repo-url> simplex_mind
```

Afterwards you should have `~/projects/simplex_mind/` sitting beside `~/projects/your-project/`.

## Step 2 — Create the virtual environment

```bash
cd simplex_mind
python3 -m venv venv
source venv/bin/activate   # bash/zsh — fish users: source venv/bin/activate.fish
pip install -r requirements.txt
```

**Windows:** don't run the above — see [SETUP-WINDOWS.md](SETUP-WINDOWS.md).

## Step 3 — Let your agent onboard the brain

Open your AI assistant **in the `simplex_mind` directory** and start a session:

- **Claude Code:** open Claude Code in `~/projects/simplex_mind`
- **Codex / Cursor / Windsurf:** open the folder with `AGENTS.md` loaded

**You don't need a magic command.** The agent checks for `database/config.json` at the start of
every session; if it's missing or onboarding isn't marked complete, it runs the onboarding flow
in [SETUP.md](SETUP.md) automatically. If it doesn't, say `run onboarding` and point it at
`SETUP.md`. (`config.json` is local state, never committed — a fresh clone not having one is
what triggers onboarding.) To check any machine's health at any time:

```bash
python3 src/utils/agent_skills/doctor.py
```

Onboarding asks for your project's path, name, ticket prefix, and goals, then writes
`projects.yaml` (local config — gitignored, never committed) and the project's reference file.

## Step 4 — Conversation history

**Claude Code: nothing to do.** Ingestion runs automatically via a Stop hook in
`.claude/settings.json` after every response.

**Other agents: the cron job is required, not optional** — they have no hook system, so this is
the only thing keeping your conversation history. Claude Code users may still want it as a
safety net for crashed sessions:

```bash
crontab -e
# Add (adjust the path if simplex_mind isn't at ~/projects/simplex_mind):
*/5 * * * * ~/projects/simplex_mind/venv/bin/python \
  ~/projects/simplex_mind/src/utils/agent_skills/conversation/conversation_ingest.py \
  >> ~/projects/simplex_mind/logs/conversation_ingest.log 2>&1
```

**Windows:** run `scripts/setup_windows_tasks.ps1` instead — it registers the equivalent
Task Scheduler jobs (per-user, no admin required).

---

## Step 5 — Check it actually worked

With the venv active, from the `simplex_mind` directory:

```bash
python3 src/utils/agent_skills/memory/session_digest.py
```

You should see a digest printing open tickets, recent decisions, active systems and recent
commits. If it runs without error, the database, config and tooling are all wired up correctly.

Then confirm semantic search is live:

```bash
python3 src/utils/agent_skills/memory/hybrid_search.py --query "test"
```

If it reports `keyword_only (semantic backend unavailable)`, `fastembed` didn't install into the
venv — activate the venv and re-run `pip install -r requirements.txt`.

## What happens from here

- **Start every session in `simplex_mind`**, not in your project folder. The agent reads the
  session digest, works out which project is active, and loads that project's instructions.
- **Which project is active is derived from the git branch** in `simplex_mind`. To switch
  projects, `git checkout <branch>`. On `master` or `develop`, no project is active.
- **To add another project**, see [Adding a Project](README.md#adding-a-project) — one brain
  serves all of them.

---

## Notes

- Run agent scripts with `python3` on Linux/macOS, or `py` on Windows
  (see [SETUP-WINDOWS.md](SETUP-WINDOWS.md))
- simplex_mind is a **sibling** of your project repos — it does not go inside them
- `CLAUDE.md` and `AGENTS.md` can coexist: the same tooling, worded for different agents.
  Your agent reads whichever applies to it.

### Semantic memory search

Runs fully locally via `fastembed`, installed by Step 2 — no API key, no extra setup.

Optional OpenAI fallback instead of the local model:

```bash
pip install openai
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```
