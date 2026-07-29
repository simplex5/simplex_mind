"""
Tool: Protocol Gate (UserPromptSubmit hook)
Purpose: Deterministic enforcement of the protocol items that instructions alone
         demonstrably fail to enforce (2026-07-26 breakdown, SIMP-D2-017).
         Principle: instructions carry routing; hooks carry enforcement.
         Response-shaped instructions fire ~100% of the time, condition-shaped
         ones ~0% — so the conditions are detected here, by code, and injected
         into context as demands at the moment they hold.

Three read-only checks per prompt:

1. Ticket cadence — 5+ tickets resolved in the active project since the last
   memory.db write -> demand a progress summary. Machine-counted via
   tickets.resolved_at vs MAX(memory_entries.created_at), scoped to entries
   tagged 'project:<name>' when a project is active (global fallback until the
   first tagged write); the agent-counted version fired 0 times in 8 closures.
2. Pending autotune candidates — re-surface mid-session. Anything announced
   only in the t=0 digest competes with the user's first request and loses.
3. Substitution detector — the harness's own auto-memory directory received a
   write more recently than memory.db while memory.db has been silent for
   hours: project facts are leaking into the wrong memory system (the exact
   failure of 2026-07-26).

Registered in .claude/settings.json under hooks.UserPromptSubmit, after
subconscious_recall.py.

Guarantees:
- Always exits 0 (fail-open) — a broken gate must never block a prompt.
- Read-only on all protocol databases (sqlite URI mode=ro); its only writes go
  to database/hooks.db — durable session throttle state plus an append-only
  event log, replacing the leaked temp-dir JSON files (SIMP-D2-038).
- Throttled: the cadence nag repeats at most every CADENCE_NAG_EVERY prompts
  while the condition holds; autotune and substitution nag once per session.
- Prints a visible `[protocol-gate: <check names>]` marker line (systemMessage)
  so the user can see in the terminal when enforcement fires (SIMP-D2-019).
- A check that raises is reported once per session as a visible
  `[protocol-gate degraded: ...]` marker (SIMP-D2-022) — fail-open must never
  mean fail-silent: a permanently broken check and a quiet healthy one are
  different states and must look different.
"""

import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from .._common import REPO_ROOT as _REPO_ROOT
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from _common import REPO_ROOT as _REPO_ROOT

try:
    from . import hook_state
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import hook_state

try:
    from .. import project_resolver
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import project_resolver

MEMORY_DB = _REPO_ROOT / "database" / "memory" / "memory.db"
AUTOTUNE_STATE = _REPO_ROOT / "database" / "memory" / "subconscious_autotune_state.json"

CADENCE_THRESHOLD = 5        # resolved tickets since last memory write that trigger the nag
CADENCE_NAG_EVERY = 10       # min prompts between repeated cadence nags
SUBSTITUTION_STALE_HOURS = 2   # memory.db must be at least this silent
SUBSTITUTION_FRESH_HOURS = 24  # auto-memory write must be at most this old
EPOCH = "1970-01-01 00:00:00"

PREAMBLE = (
    "<protocol-gate> Deterministic protocol checks fired — these conditions were "
    "detected by code just now (database queries and file timestamps, not "
    "conversational inference). Act on each demand as part of handling this "
    "prompt; they are not optional.\n"
)


def _read_only(db_path: Path):
    """Open a SQLite DB read-only; raises if missing (caller catches)."""
    return sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)


def _last_memory_write(project: str = None) -> str:
    """UTC 'YYYY-MM-DD HH:MM:SS' of the newest memory.db entry, or EPOCH.
    With a project name, prefer entries tagged 'project:<name>' (memory_write
    auto-tags them, SIMP-D2-022) so a write about another project can't
    suppress this project's cadence. Falls back to the global max while no
    tagged entries exist yet — the transition period before the first tagged
    write per project."""
    con = _read_only(MEMORY_DB)
    try:
        if project:
            row = con.execute(
                "SELECT MAX(created_at) FROM memory_entries WHERE tags LIKE ?",
                (f'%"project:{project}"%',),
            ).fetchone()
            if row[0]:
                return row[0]
        row = con.execute("SELECT MAX(created_at) FROM memory_entries").fetchone()
        return row[0] or EPOCH
    finally:
        con.close()


def check_cadence(last_mem: str, state: dict) -> str:
    """5+ tickets resolved since the last memory write -> progress-summary demand."""
    if state["prompts"] - state.get("cadence_last_nag", -CADENCE_NAG_EVERY) < CADENCE_NAG_EVERY:
        return ""
    tickets_db = project_resolver.get_ticket_db_path(None)
    con = _read_only(Path(tickets_db))
    try:
        n = con.execute(
            "SELECT COUNT(*) FROM tickets WHERE resolved_at IS NOT NULL AND resolved_at > ?",
            (last_mem,),
        ).fetchone()[0]
    finally:
        con.close()
    if n < CADENCE_THRESHOLD:
        return ""
    state["cadence_last_nag"] = state["prompts"]
    return (
        f"- CADENCE: {n} tickets have been resolved since the last memory.db write. "
        f"Write a session progress summary NOW via memory_write.py (decisions, "
        f"corrections, systems touched), then continue with the user's request."
    )


def check_autotune(state: dict) -> str:
    """Pending subconscious keyword candidates -> surface them, once per session."""
    if "autotune" in state["once"]:
        return ""
    if not AUTOTUNE_STATE.exists():
        return ""  # autotune never ran on this machine — nothing pending, not an error
    pending = json.loads(AUTOTUNE_STATE.read_text(encoding="utf-8")).get("pending", [])
    if not pending:
        return ""
    state["once"].append("autotune")
    return (
        f"- PENDING CANDIDATES: {len(pending)} subconscious keyword candidates await "
        f"review. Propose them to the user this session "
        f"(subconscious_autotune.py --review, then --approve/--reject)."
    )


def check_substitution(last_mem: str, state: dict) -> str:
    """Harness auto-memory written more recently than a stale memory.db -> routing demand."""
    if "substitution" in state["once"]:
        return ""
    # The harness's auto-memory dir name is the launch dir with :\/_. munged to '-'
    munged = re.sub(r"[:\\/_.]", "-", str(_REPO_ROOT))
    automem = Path.home() / ".claude" / "projects" / munged / "memory"
    newest = max((f.stat().st_mtime for f in automem.glob("*.md")), default=0.0)
    last_mem_ts = (
        datetime.strptime(last_mem, "%Y-%m-%d %H:%M:%S")
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )
    now = time.time()
    stale = (now - last_mem_ts) > SUBSTITUTION_STALE_HOURS * 3600
    fresh_automem = newest > 0 and (now - newest) < SUBSTITUTION_FRESH_HOURS * 3600
    if not (stale and fresh_automem and newest > last_mem_ts):
        return ""
    state["once"].append("substitution")
    hours = int((now - last_mem_ts) / 3600)
    return (
        f"- MEMORY ROUTING (file-mtime evidence — the timestamps are measured, the "
        f"routing conclusion is inferred): the harness auto-memory directory was "
        f"written more recently than memory.db, and memory.db has been silent for "
        f"{hours}h. Auto-memory is for agent-workflow notes only — check whether "
        f"project facts, decisions, corrections or preferences were routed there, "
        f"and mirror anything project-related into memory.db via memory_write.py now."
    )


def main() -> int:
    t0 = time.time()
    # utf-8-sig: some Windows pipe paths prepend a BOM, which json.load rejects
    data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    session_id = re.sub(r"[^A-Za-z0-9_-]", "_", str(data.get("session_id", "unknown")))[:64]

    state = {"prompts": 0, "once": []}
    loaded = hook_state.get_state("protocol_gate", session_id)
    if isinstance(loaded, dict):
        state.update(loaded)
    state["prompts"] = int(state.get("prompts", 0)) + 1

    # last_mem = None means memory.db itself is unreadable: the checks that
    # depend on it are skipped (their preconditions are unmeasurable) and the
    # failure is surfaced as a degraded marker instead of vanishing.
    # Cadence scopes to the active project's tagged entries; substitution is
    # about the whole DB being silent, so it stays global (SIMP-D2-022).
    last_mem_global = None
    last_mem_cadence = None
    errors = []  # (check name, error type)
    try:
        active = project_resolver.get_active_project()
        project = active["name"] if active else None
    except Exception:
        project = None
    try:
        last_mem_global = _last_memory_write()
        last_mem_cadence = _last_memory_write(project) if project else last_mem_global
    except Exception as e:
        errors.append(("memory", type(e).__name__))

    demands = []  # (check name, message)
    for name, check in (
        ("cadence", lambda: check_cadence(last_mem_cadence, state) if last_mem_cadence else ""),
        ("autotune", lambda: check_autotune(state)),
        ("substitution", lambda: check_substitution(last_mem_global, state) if last_mem_global else ""),
    ):
        try:
            msg = check()
            if msg:
                demands.append((name, msg))
        except Exception as e:  # each check fails open independently — but visibly
            errors.append((name, type(e).__name__))

    # A permanently-broken check must be distinguishable from a quiet one:
    # surface each erroring check once per session (SIMP-D2-022).
    reported = state.setdefault("errors_reported", [])
    fresh_errors = [(n, t) for n, t in errors if n not in reported]
    reported.extend(n for n, _ in fresh_errors)

    hook_state.set_state("protocol_gate", session_id, state)

    # Observability rows (SIMP-D2-038): one per check outcome + one invocation
    # summary carrying duration. All fail-open inside hook_state.
    for n, _ in demands:
        hook_state.log_event("protocol_gate", session_id, n, "fired")
    for n, t in errors:
        hook_state.log_event("protocol_gate", session_id, n, "degraded", reason=t)
    hook_state.log_event(
        "protocol_gate", session_id, "invocation",
        "fired" if demands else "skipped",
        reason=",".join(n for n, _ in demands),
        duration_ms=int((time.time() - t0) * 1000))

    out = {}
    if demands:
        out["systemMessage"] = "[protocol-gate: " + ", ".join(n for n, _ in demands) + "]"
        out["hookSpecificOutput"] = {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": (
                PREAMBLE + "\n".join(m for _, m in demands) + "\n</protocol-gate>"
            ),
        }
    if fresh_errors:
        degraded = ("[protocol-gate degraded: "
                    + ", ".join(f"{n} check failed ({t})" for n, t in fresh_errors)
                    + " — run doctor.py]")
        out["systemMessage"] = (out.get("systemMessage", "") + " " + degraded).strip()
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail-open, always
