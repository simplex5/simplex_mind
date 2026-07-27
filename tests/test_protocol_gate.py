"""Protocol gate hook I/O contract (SIMP-D2-022): always exit 0, stdout is
empty or one JSON object, broken checks surface once per session as a
degraded marker, missing autotune state is a clean skip."""
import io
import json
import sqlite3
import sys
from types import SimpleNamespace

import pytest

from memory import protocol_gate


@pytest.fixture
def gate_env(tmp_path, monkeypatch, fake_projects, on_branch):
    """Healthy gate environment on temp state: valid empty memory.db, valid
    empty tickets.db for the active project, no autotune file, temp throttle
    dir. Returns a runner: run(session_id) -> (exit_code, parsed_stdout|None)."""
    mem_db = tmp_path / "memory.db"
    con = sqlite3.connect(mem_db)
    con.execute("CREATE TABLE memory_entries (created_at TEXT, tags TEXT)")
    con.commit()
    con.close()
    monkeypatch.setattr(protocol_gate, "MEMORY_DB", mem_db)
    monkeypatch.setattr(protocol_gate, "AUTOTUNE_STATE", tmp_path / "autotune_state.json")
    # keep the substitution check off this machine's real harness auto-memory dir
    monkeypatch.setattr(protocol_gate, "_REPO_ROOT", tmp_path)

    tickets_db = fake_projects["proj_dir"] / "database" / "tickets.db"
    con = sqlite3.connect(tickets_db)
    con.execute("CREATE TABLE tickets (resolved_at TEXT)")
    con.commit()
    con.close()
    on_branch("alpha-branch")  # active project: alpha -> tickets_db above

    import tempfile
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

    def run(session_id="s1"):
        payload = json.dumps({"session_id": session_id}).encode()
        monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(payload)))
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = protocol_gate.main()
        out = buf.getvalue().strip()
        return rc, (json.loads(out) if out else None)

    return SimpleNamespace(run=run, mem_db=mem_db, tickets_db=tickets_db, tmp=tmp_path)


def test_healthy_quiet_prompt(gate_env):
    rc, out = gate_env.run()
    assert rc == 0
    assert out is None  # nothing to demand, nothing degraded


def test_missing_autotune_state_is_clean_skip(gate_env):
    # regression: this used to raise FileNotFoundError on every prompt
    rc, out = gate_env.run("skipcheck")
    assert rc == 0
    assert out is None


def test_corrupt_memory_db_degrades_visibly_once(gate_env):
    gate_env.mem_db.write_bytes(b"not a sqlite file")
    rc, out = gate_env.run("deg1")
    assert rc == 0
    assert out is not None
    assert "degraded" in out["systemMessage"]
    assert "memory check failed" in out["systemMessage"]
    assert "doctor" in out["systemMessage"]
    # second prompt, same session: already reported, stays quiet
    rc, out = gate_env.run("deg1")
    assert rc == 0
    assert out is None


def test_cadence_demand_fires(gate_env):
    con = sqlite3.connect(gate_env.tickets_db)
    con.executemany("INSERT INTO tickets (resolved_at) VALUES (?)",
                    [("2099-01-01 00:00:00",)] * 5)
    con.commit()
    con.close()
    rc, out = gate_env.run("cad1")
    assert rc == 0
    assert out["systemMessage"].startswith("[protocol-gate: cadence]")
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "CADENCE: 5 tickets" in ctx
    assert "<protocol-gate>" in ctx and "</protocol-gate>" in ctx
    assert "not inferred" not in ctx  # honest preamble (SIMP-D2-022)


def test_stdout_is_single_json_object(gate_env):
    con = sqlite3.connect(gate_env.tickets_db)
    con.executemany("INSERT INTO tickets (resolved_at) VALUES (?)",
                    [("2099-01-01 00:00:00",)] * 5)
    con.commit()
    con.close()
    gate_env.mem_db.write_bytes(b"corrupt")  # demand + degraded in same prompt
    rc, out = gate_env.run("both1")
    assert rc == 0
    # memory.db corrupt -> cadence/substitution skipped, so only degraded marker
    assert "degraded" in out["systemMessage"]


def test_autotune_pending_surfaces_once(gate_env):
    (gate_env.tmp / "autotune_state.json").write_text(
        json.dumps({"pending": [{"piece": "p", "phrase": "x"}]}), encoding="utf-8")
    rc, out = gate_env.run("auto1")
    assert rc == 0
    assert "[protocol-gate: autotune]" in out["systemMessage"]
    assert "1 subconscious keyword candidates" in out["hookSpecificOutput"]["additionalContext"]
    rc, out = gate_env.run("auto1")  # once per session
    assert out is None
