"""Ticket gate PreToolUse hook contract (SIMP-D2-039): warn-once when a
file-editing tool starts with no open ticket, silent when one exists, silent
for unmanaged paths, fail-open on malformed input, never a permissionDecision
(that would alter the harness's permission flow)."""
import io
import json
import sqlite3
import sys
from types import SimpleNamespace

import pytest

from memory import hook_state
from tickets import pretooluse_gate


@pytest.fixture
def ticket_gate_env(tmp_path, monkeypatch, fake_projects, on_branch):
    """Active project alpha with an empty (zero-ticket) tickets.db, temp
    hooks.db, brain root fenced to a temp dir."""
    brain_root = tmp_path / "brainroot"
    brain_root.mkdir()
    monkeypatch.setattr(pretooluse_gate, "_REPO_ROOT", brain_root)
    monkeypatch.setattr(hook_state, "DB_PATH", tmp_path / "hooks.db")

    tickets_db = fake_projects["proj_dir"] / "database" / "tickets.db"
    con = sqlite3.connect(tickets_db)
    con.execute("CREATE TABLE tickets (status TEXT)")
    con.commit()
    con.close()
    on_branch("alpha-branch")

    project_file = fake_projects["proj_dir"] / "src" / "thing.py"

    def run(session_id="s1", tool_name="Edit", file_path=None, raw=None):
        payload = raw if raw is not None else json.dumps({
            "session_id": session_id,
            "tool_name": tool_name,
            "tool_input": {"file_path": str(file_path or project_file)},
            "cwd": str(fake_projects["proj_dir"]),
        }).encode()
        monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(payload)))
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = pretooluse_gate.main()
        out = buf.getvalue().strip()
        return rc, (json.loads(out) if out else None)

    return SimpleNamespace(run=run, tickets_db=tickets_db, tmp=tmp_path,
                           project_file=project_file)


def _events(tmp):
    con = sqlite3.connect(tmp / "hooks.db")
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT outcome, reason FROM hook_events WHERE hook='ticket_gate'").fetchall()
    con.close()
    return [(r["outcome"], r["reason"]) for r in rows]


def test_no_ticket_warns_once_then_stays_quiet(ticket_gate_env):
    rc, out = ticket_gate_env.run("w1")
    assert rc == 0
    assert "[ticket-gate: no open ticket" in out["systemMessage"]
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "<ticket-gate>" in ctx and "ticket_create" in ctx
    assert "permissionDecision" not in json.dumps(out)  # never touches permissions

    rc, out = ticket_gate_env.run("w1")  # same session: once only
    assert rc == 0 and out is None
    outcomes = _events(ticket_gate_env.tmp)
    assert ("fired", "no-open-ticket") in outcomes
    assert ("skipped", "already-warned") in outcomes


def test_open_ticket_keeps_gate_silent(ticket_gate_env):
    con = sqlite3.connect(ticket_gate_env.tickets_db)
    con.execute("INSERT INTO tickets (status) VALUES ('open')")
    con.commit()
    con.close()
    rc, out = ticket_gate_env.run("q1")
    assert rc == 0 and out is None
    assert ("skipped", "open-ticket-exists") in _events(ticket_gate_env.tmp)


def test_in_progress_ticket_also_satisfies(ticket_gate_env):
    con = sqlite3.connect(ticket_gate_env.tickets_db)
    con.execute("INSERT INTO tickets (status) VALUES ('in_progress')")
    con.commit()
    con.close()
    rc, out = ticket_gate_env.run("q2")
    assert rc == 0 and out is None


def test_unmanaged_path_is_none_of_the_gates_business(ticket_gate_env):
    scratch = ticket_gate_env.tmp / "scratch" / "notes.md"
    rc, out = ticket_gate_env.run("p1", file_path=scratch)
    assert rc == 0 and out is None
    assert ("skipped", "outside-managed-paths") in _events(ticket_gate_env.tmp)


def test_ungated_tool_is_skipped(ticket_gate_env):
    rc, out = ticket_gate_env.run("t1", tool_name="Read")
    assert rc == 0 and out is None
    assert ("skipped", "ungated-tool") in _events(ticket_gate_env.tmp)


def test_malformed_stdin_fails_open(ticket_gate_env):
    rc, out = ticket_gate_env.run(raw=b"not json at all")
    assert rc == 0 and out is None


def test_unreadable_ticket_db_degrades_visibly_once(ticket_gate_env):
    ticket_gate_env.tickets_db.write_bytes(b"corrupt")
    rc, out = ticket_gate_env.run("d1")
    assert rc == 0
    assert "degraded" in out["systemMessage"]
    rc, out = ticket_gate_env.run("d1")  # reported once per session
    assert rc == 0 and out is None
