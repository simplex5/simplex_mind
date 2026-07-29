"""hook_state store (SIMP-D2-038): durable per-session hook state + append-only
event log in database/hooks.db, replacing the temp-dir JSON files that leaked
forever and died on temp wipes. Contract under test: round-trip fidelity,
bounded retention, and fail-open on a broken DB."""
import pytest

from memory import hook_state


@pytest.fixture
def hooks_db(tmp_path, monkeypatch):
    monkeypatch.setattr(hook_state, "DB_PATH", tmp_path / "hooks.db")
    return hook_state


def test_state_round_trip_and_isolation(hooks_db):
    assert hooks_db.get_state("gate", "s1") is None
    assert hooks_db.get_state("gate", "s1", default=[]) == []
    assert hooks_db.set_state("gate", "s1", {"prompts": 3, "once": ["a"]})
    assert hooks_db.get_state("gate", "s1") == {"prompts": 3, "once": ["a"]}
    hooks_db.set_state("gate", "s1", {"prompts": 4, "once": []})  # upsert replaces
    assert hooks_db.get_state("gate", "s1")["prompts"] == 4
    assert hooks_db.get_state("other-hook", "s1") is None  # keyed per hook
    assert hooks_db.get_state("gate", "s2") is None        # and per session


def test_log_event_and_retention_prune(hooks_db):
    assert hooks_db.log_event("gate", "s1", "cadence", "fired", reason="x", duration_ms=12)
    conn = hooks_db.get_connection()
    conn.execute(
        "INSERT INTO hook_events (session_id, hook, check_name, outcome, created_at) "
        "VALUES ('ancient', 'gate', 'c', 'fired', datetime('now', '-365 days'))")
    conn.commit()
    conn.close()
    hooks_db.log_event("gate", "s1", "invocation", "skipped")  # prunes on write
    conn = hooks_db.get_connection()
    ids = {r["session_id"] for r in conn.execute("SELECT session_id FROM hook_events")}
    conn.close()
    assert "ancient" not in ids  # past RETENTION_DAYS -> pruned
    assert "s1" in ids


def test_fail_open_when_db_path_is_a_directory(tmp_path, monkeypatch):
    bad = tmp_path / "not-a-db"
    bad.mkdir()
    monkeypatch.setattr(hook_state, "DB_PATH", bad)
    assert hook_state.get_state("g", "s", default="fallback") == "fallback"
    assert hook_state.set_state("g", "s", {"x": 1}) is False
    assert hook_state.log_event("g", "s") is False


def test_hooks_carry_no_tempfile_state():
    """The plan's grep check as a regression test: neither hook may reintroduce
    temp-dir session state."""
    import inspect
    from memory import protocol_gate
    from subconscious import subconscious_recall
    assert "tempfile" not in inspect.getsource(protocol_gate)
    assert "tempfile" not in inspect.getsource(subconscious_recall)
