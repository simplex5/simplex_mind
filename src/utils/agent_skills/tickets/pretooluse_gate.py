"""
Tool: Ticket Gate (PreToolUse hook — SIMP-D2-039)
Purpose: Deterministic enforcement of the hardest rule in CLAUDE.md — "create a
         ticket before any work that edits files. No exceptions." That rule is
         condition-shaped prose, and the SIMP-D2-017 analysis measured that
         condition-shaped instructions fire ~0% of the time. protocol_gate
         proved the fix: detect the condition in code, inject the demand.

Fires on Edit/Write/NotebookEdit tool calls (settings.json matcher). When the
active project's ticket DB (brain DB on master/develop) has NO open or
in_progress ticket, it injects a warn-once demand to create one.

v1 is warn-only, never deny: every decision is logged to hooks.db, and that
false-positive record is what justifies (or vetoes) a future deny mode.
Bash-mutation detection is explicitly out of scope — classifying which Bash
commands mutate files is a false-positive minefield.

Guarantees:
- Always exits 0 (fail-open) — a broken gate must never block an edit.
- Never emits a permissionDecision: the harness's normal permission flow is
  untouched (an accidental "allow" would silently bypass the user's prompts).
- Read-only on the ticket DB; its only writes go to database/hooks.db.
- Warns at most once per session; repeated no-ticket edits stay silent.
- Skips paths outside the brain repo and all registered project paths —
  scratchpads, plan files, and harness auto-memory need no tickets.
- Visible markers: `[ticket-gate: no open ticket]` on warn,
  `[ticket-gate degraded: ...]` once per session when the check itself breaks.
"""

import json
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from .. import project_resolver
    from ..memory import hook_state
    from .._common import REPO_ROOT as _REPO_ROOT
except ImportError:
    import project_resolver
    from _common import REPO_ROOT as _REPO_ROOT
    from memory import hook_state

GATED_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}

DEMAND = (
    "<ticket-gate> Deterministic protocol check (SIMP-D2-039): a file-editing "
    "tool call is starting but the active ticket DB has NO open or in_progress "
    "ticket. CLAUDE.md hard rule: create a ticket before any work that edits "
    "files. Create one NOW via ticket_create.py (or simplex ticket create) "
    "before continuing — this warning fires once per session. </ticket-gate>"
)


def _managed_roots() -> list:
    """The brain repo + every registered project path — the places where the
    ticket rule applies. Everything else (scratchpads, plan files, harness
    config) is none of this gate's business."""
    roots = [Path(_REPO_ROOT).resolve()]
    try:
        for proj in project_resolver.get_all_projects():
            try:
                roots.append(Path(proj["path"]).expanduser().resolve())
            except OSError:
                continue
    except Exception:
        pass  # resolver trouble → gate still guards the brain repo itself
    return roots


def _target_path(data: dict) -> Path:
    """Best-effort path of the file being edited, resolved against the hook's cwd."""
    tool_input = data.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = Path(data.get("cwd") or ".") / p
    return p.resolve()


def _has_open_ticket() -> bool:
    """Read-only count in the routed ticket DB (active project, brain fallback)."""
    db_path = Path(project_resolver.get_ticket_db_path(None))
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        (n,) = con.execute(
            "SELECT COUNT(*) FROM tickets WHERE status IN ('open', 'in_progress')"
        ).fetchone()
        return n > 0
    finally:
        con.close()


def main() -> int:
    t0 = time.time()
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    except Exception:
        return 0  # unparseable hook payload — nothing sane to do, fail open
    session_id = re.sub(r"[^A-Za-z0-9_-]", "_", str(data.get("session_id", "unknown")))[:64]

    def _done(outcome: str, reason: str = "") -> int:
        hook_state.log_event("ticket_gate", session_id, "invocation", outcome,
                             reason=reason, duration_ms=int((time.time() - t0) * 1000))
        return 0

    if data.get("tool_name") not in GATED_TOOLS:
        return _done("skipped", "ungated-tool")

    state = hook_state.get_state("ticket_gate", session_id) or {}

    target = _target_path(data)
    if target is not None:
        try:
            if not any(target.is_relative_to(root) for root in _managed_roots()):
                return _done("skipped", "outside-managed-paths")
        except Exception:
            pass  # containment check trouble → treat as managed, keep checking

    try:
        if _has_open_ticket():
            return _done("skipped", "open-ticket-exists")
    except Exception as e:
        if not state.get("degraded_reported"):
            state["degraded_reported"] = True
            hook_state.set_state("ticket_gate", session_id, state)
            print(json.dumps({"systemMessage":
                              f"[ticket-gate degraded: ticket DB unreadable ({type(e).__name__}) "
                              f"— run doctor.py]"}))
        return _done("degraded", type(e).__name__)

    if state.get("warned"):
        return _done("skipped", "already-warned")
    state["warned"] = True
    hook_state.set_state("ticket_gate", session_id, state)

    print(json.dumps({
        "systemMessage": "[ticket-gate: no open ticket — demanded one before this edit]",
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": DEMAND,
        },
    }))
    return _done("fired", "no-open-ticket")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail-open, always
