"""ticket_list CLI output contract (SIMP-D2-054): table-only default, --json
opt-in, truncation banner as the first stdout line, --limit 0 = unlimited —
including the list_tickets_all merge-path regression where limit=-1 would
slice [:-1] and silently drop the last merged ticket."""
import json
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TICKETS_DIR = REPO_ROOT / "src" / "utils" / "agent_skills" / "tickets"
if str(TICKETS_DIR) not in sys.path:
    # ticket_list uses script-mode imports (`from ticket_db import ...`);
    # recreate that environment the same way simplex_cli._ensure_skills_path does.
    sys.path.insert(0, str(TICKETS_DIR))

import ticket_db  # noqa: E402
import ticket_list  # noqa: E402

import project_resolver  # noqa: E402


def run_cli(monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", ["ticket_list.py", *argv])
    ticket_list.main()
    return capsys.readouterr().out


def json_block(out: str) -> dict:
    return json.loads(out[out.index("{"):])


@pytest.fixture
def two_fake_projects(tmp_path, monkeypatch):
    """Two registered projects with their own ticket DBs — list_tickets_all's
    merge path only exists with more than one DB."""
    dirs = {}
    for name in ("alpha", "beta"):
        d = tmp_path / f"proj_{name}"
        (d / "database").mkdir(parents=True)
        dirs[name] = d
    yaml_path = tmp_path / "projects.yaml"
    yaml_path.write_text(textwrap.dedent(f"""\
        machine: T9
        projects:
          alpha:
            path: {dirs['alpha']}
            ref_file: CLAUDE.md.ref
            ticket_prefix: ALPH
            branch: alpha-branch
          beta:
            path: {dirs['beta']}
            ref_file: CLAUDE.md.ref
            ticket_prefix: BETA
            branch: beta-branch
    """))
    monkeypatch.setattr(project_resolver, "_PROJECTS_YAML", yaml_path)
    monkeypatch.setattr(project_resolver, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(project_resolver, "_projects_cache", None)
    monkeypatch.setattr(project_resolver, "_machine_cache", ...)
    monkeypatch.setattr(project_resolver, "_branch_cache", ...)
    # The implicit brain entry bakes str(_REPO_ROOT) at import time, so the
    # _REPO_ROOT patch above does not reach it — without this, list_tickets_all
    # reads the REAL simplex_mind tickets.db into the merge.
    monkeypatch.setitem(project_resolver._SIMPLEX_MIND_ENTRY,
                        "path", str(tmp_path / "brain"))
    return dirs


def test_default_output_is_table_only(fake_projects, monkeypatch, capsys):
    a = ticket_db.create_ticket("task", "First open", target="alpha")["id"]
    b = ticket_db.create_ticket("bug", "Second open", target="alpha")["id"]
    out = run_cli(monkeypatch, capsys, "--target", "alpha")
    assert a in out and b in out
    assert "2 of 2 ticket(s) shown" in out
    assert '"success"' not in out          # no JSON block by default
    assert "TRUNCATED" not in out


def test_json_flag_restores_block(fake_projects, monkeypatch, capsys):
    ticket_db.create_ticket("task", "One", target="alpha")
    out = run_cli(monkeypatch, capsys, "--target", "alpha", "--json")
    data = json_block(out)
    assert data["success"] is True
    assert data["total"] == 1
    assert data["limit"] == 50


def test_banner_is_first_line_when_truncated(fake_projects, monkeypatch, capsys):
    for i in range(3):
        ticket_db.create_ticket("task", f"T{i}", target="alpha")
    out = run_cli(monkeypatch, capsys, "--target", "alpha", "--limit", "2")
    assert out.splitlines()[0].startswith("!! TRUNCATED: showing 2 of 3")
    assert "2 of 3 ticket(s) shown" in out


def test_limit_zero_returns_all_rows(fake_projects, monkeypatch, capsys):
    ids = [ticket_db.create_ticket("task", f"T{i}", target="alpha")["id"]
           for i in range(3)]
    out = run_cli(monkeypatch, capsys, "--target", "alpha", "--limit", "0", "--json")
    assert all(tid in out for tid in ids)
    assert "TRUNCATED" not in out
    data = json_block(out)
    assert len(data["tickets"]) == 3
    assert data["limit"] == 0              # caller's value, not the internal -1


def test_all_projects_limit_zero_keeps_last_merged_ticket(
        two_fake_projects, monkeypatch, capsys):
    # High-priority tickets in alpha, one LOW-priority in beta: the beta ticket
    # sorts last after the merge, exactly the row the unguarded [:-1] slice drops.
    for i in range(2):
        ticket_db.create_ticket("task", f"A{i}", priority="high", target="alpha")
    last = ticket_db.create_ticket("task", "B-last", priority="low", target="beta")["id"]
    out = run_cli(monkeypatch, capsys, "--all-projects", "--all", "--limit", "0")
    assert last in out
    assert "3 of 3 ticket(s) shown" in out
    assert "TRUNCATED" not in out
