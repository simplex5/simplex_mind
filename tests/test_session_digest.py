"""Digest failure paths: broken subsystems must render as UNAVAILABLE, never
as healthy emptiness (SIMP-D2-022); lost-config seam prints repair line
(SIMP-D2-021)."""
import pytest

from memory import session_digest


def _raise(*args, **kwargs):
    raise RuntimeError("db exploded")


@pytest.fixture(autouse=True)
def isolated_digest(fake_repo, monkeypatch):
    """Every test starts from healthy stubs on a temp root (never the real
    DBs), then breaks exactly the piece under test."""
    root = fake_repo(config={"onboarding_complete": True})
    monkeypatch.setattr(session_digest, "PROJECT_ROOT", root)
    monkeypatch.setattr(session_digest, "_ticket_list",
                        lambda **kw: {"success": True, "tickets": []})
    monkeypatch.setattr(session_digest, "_get_active", None)
    monkeypatch.setattr(session_digest, "list_entries",
                        lambda **kw: {"success": True, "entries": []})
    return root


def test_broken_ticket_list_renders_unavailable(monkeypatch):
    monkeypatch.setattr(session_digest, "_ticket_list", _raise)
    out = session_digest.generate_digest()
    assert "Open: UNAVAILABLE" in out
    assert "db exploded" in out
    assert "Open: 0" not in out


def test_failed_ticket_query_renders_unavailable(monkeypatch):
    monkeypatch.setattr(session_digest, "_ticket_list",
                        lambda **kw: {"success": False, "error": "no such table: tickets"})
    out = session_digest.generate_digest()
    assert "Open: UNAVAILABLE" in out
    assert "no such table" in out


def test_missing_ticket_tooling_renders_unavailable(monkeypatch):
    monkeypatch.setattr(session_digest, "_ticket_list", None)
    out = session_digest.generate_digest()
    assert "Open: UNAVAILABLE" in out
    assert "import failed" in out


def test_healthy_zero_tickets_render_as_zero():
    out = session_digest.generate_digest()
    assert "Open: 0" in out
    assert "UNAVAILABLE" not in out.split("## Tickets")[1].split("##")[0]


def test_failed_memory_query_renders_unavailable(monkeypatch):
    monkeypatch.setattr(session_digest, "list_entries",
                        lambda **kw: {"success": False, "error": "memory.db locked"})
    out = session_digest.generate_digest()
    assert "## Recent Decisions" in out
    assert "UNAVAILABLE — memory.db locked" in out


def test_healthy_empty_decisions_stay_silent():
    # emptiness is quiet; only *errors* are loud
    out = session_digest.generate_digest()
    assert "## Recent Decisions" not in out


def test_lost_config_prints_repair_line(isolated_digest, monkeypatch):
    (isolated_digest / "database" / "config.json").unlink()
    (isolated_digest / "database" / "memory" / "memory.db").touch()
    out = session_digest.generate_digest()
    assert "CONFIG LOST" in out
    assert "--mark-onboarded" in out
    assert "do NOT re-run onboarding" in out


def test_fresh_clone_prints_onboarding_line(isolated_digest):
    (isolated_digest / "database" / "config.json").unlink()
    out = session_digest.generate_digest()
    assert "ONBOARDING INCOMPLETE" in out
    assert "SETUP.md" in out
