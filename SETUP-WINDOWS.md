# SETUP-WINDOWS.md: simplex_mind on Native Windows

Windows companion to [SETUP.md](SETUP.md). Follow SETUP.md's onboarding flow, applying
the substitutions below. Everything here assumes **Git Bash** (installed with Git for
Windows) as the working shell. Claude Code also uses Git Bash to run its shell
commands and hooks on Windows, so one shell covers everything.

---

## Prerequisites

1. **Git for Windows**: https://git-scm.com/downloads/win
   Required. It provides Git Bash, which Claude Code uses as its shell and hook
   runner on Windows. Without it Claude Code falls back to PowerShell and the
   committed hooks will not work.
2. **Python 3.11+ from python.org**: https://www.python.org/downloads/windows/
   Keep the **"py launcher"** component selected in the installer (it is on by
   default). The hooks and this guide invoke Python as `py` on Windows.
   Do NOT rely on the `python3` command; on Windows that name is usually the
   Microsoft Store redirect stub, not a real interpreter.
3. **Claude Code**: install per https://code.claude.com/docs/en/setup

## Interpreter convention

Wherever SETUP.md, CLAUDE.md, or other docs say `python3`, type `py` instead.
The committed hooks in `.claude/settings.json` already select the right
interpreter automatically (`python3` on Linux/macOS, `py` on Windows).

## Clone, identity, virtual environment

```bash
cd ~/projects            # Git Bash maps ~ to C:\Users\<you>
git clone <remote> simplex_mind    # clones master (stable)
cd simplex_mind
git config user.name "simplex5"
git config user.email "dev@simplex5.com"
py -m venv venv
source venv/Scripts/activate       # Windows venv layout (not venv/bin/activate)
pip install -r requirements.txt
```

**Git identity is mandatory before any commit or push:** author must always be
`simplex5 <dev@simplex5.com>`, never a real name. Verify with `git config user.name`
before the first push from this machine.

Where SETUP.md references `venv/bin/python` or `venv/bin/pip`, the Windows
equivalents are `venv/Scripts/python.exe` and `venv/Scripts/pip.exe`.

## Onboarding differences

Run SETUP.md's New Project Flow with these changes:

- **Step 2b (Machine identifier):** use this machine's ID (e.g. `D2` for a second
  desktop) as the top-level `machine:` key in `projects.yaml`.
- **Step 8 (cron):** Windows has no cron. The Task Scheduler equivalents are set up
  with one command (per-user, no admin, idempotent; requires the venv from above):
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\setup_windows_tasks.ps1
  ```
  This registers `SimplexMind-Ingest` (every 5 min — crash-recovery safety net; the
  **Stop hook** remains the primary ingest path) and `SimplexMind-Autotune`
  (Sunday 04:00 weekly keyword mining). Both run the venv's `pythonw.exe`
  windowless and log to `logs/`. Skipping this is acceptable: ingest still works
  via the Stop hook; autotune would then only run manually
  (`py src/utils/agent_skills/subconscious/subconscious_autotune.py`).

## Verify the transcript ingest

Claude Code names its transcript folders under `~/.claude/projects/` with an
undocumented encoding on Windows, so simplex_mind does not guess it: on Windows,
`conversation_ingest.py` *discovers* the right folders by reading the `cwd`
field inside the transcripts themselves. Verify it works:

1. Have at least one short Claude Code conversation in the simplex_mind directory.
2. Run:
   ```bash
   py src/utils/agent_skills/conversation/conversation_ingest.py --dry-run
   ```
3. Confirm it reports at least 1 file processed and 1 session. Zero everything
   means discovery found no matching transcript folder: check that
   `~/.claude/projects/` exists and contains a folder with `.jsonl` files whose
   `cwd` matches this repo's path, then open a ticket.

## Known Windows limitations

- Scheduled tasks run only while the user is logged on (per-user tasks, interactive
  token). Missed runs fire at next opportunity (`StartWhenAvailable`).
- The statusline token tracker (`track_tokens.py --claude-delta`) depends on a
  user-side statusline script; state files live in `%TEMP%` instead of `/tmp`.
