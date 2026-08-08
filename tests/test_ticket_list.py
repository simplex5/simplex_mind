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


# --- SIMP-D2-055: --query LIKE search ---------------------------------------


def test_query_matches_title_and_description(fake_projects, monkeypatch, capsys):
    t1 = ticket_db.create_ticket("task", "Campfire smoke pass", target="alpha")["id"]
    t2 = ticket_db.create_ticket("task", "Unrelated title",
                                 description="the campfire founds a town",
                                 target="alpha")["id"]
    t3 = ticket_db.create_ticket("task", "Nothing to do with it", target="alpha")["id"]
    out = run_cli(monkeypatch, capsys, "--target", "alpha", "--query", "campfire")
    assert t1 in out and t2 in out and t3 not in out
    assert "2 of 2 ticket(s) shown" in out
    # description-only match gets a context line; title match does not
    assert f"  {t2}: " in out
    assert "founds a town" in out
    assert f"  {t1}: " not in out


def test_query_includes_done_by_default_respects_explicit_status(
        fake_projects, monkeypatch, capsys):
    tid = ticket_db.create_ticket("task", "widget polish", target="alpha")["id"]
    ticket_db.update_ticket(tid, target="alpha", status="done")
    out = run_cli(monkeypatch, capsys, "--target", "alpha", "--query", "widget")
    assert tid in out                     # duplicate checks must see closed tickets
    out = run_cli(monkeypatch, capsys, "--target", "alpha", "--query", "widget",
                  "--status", "open")
    assert tid not in out                 # explicit --status still wins


def test_query_case_insensitive(fake_projects, monkeypatch, capsys):
    tid = ticket_db.create_ticket("task", "CAMPFIRE radius", target="alpha")["id"]
    out = run_cli(monkeypatch, capsys, "--target", "alpha", "--query", "campfire")
    assert tid in out


def test_query_escapes_like_wildcards(fake_projects, monkeypatch, capsys):
    ticket_db.create_ticket("task", "50% done", target="alpha")
    hit = ticket_db.create_ticket("task", "100% done", target="alpha")["id"]
    out = run_cli(monkeypatch, capsys, "--target", "alpha", "--query", "100%")
    assert hit in out
    assert "1 of 1 ticket(s) shown" in out    # unescaped % would match both


def test_query_literal_percent_description_context(fake_projects, monkeypatch, capsys):
    tid = ticket_db.create_ticket("task", "Unrelated title",
                                  description="progress is 100% complete today",
                                  target="alpha")["id"]
    out = run_cli(monkeypatch, capsys, "--target", "alpha", "--query", "100%")
    # context finder must search the raw query, not the escaped pattern
    assert f"  {tid}: " in out
    assert "100% complete" in out


def test_query_unclipped_long_title(fake_projects, monkeypatch, capsys):
    long_title = "A very long ticket title that keeps going " * 2 + "ENDMARKER"
    assert len(long_title) > 60
    ticket_db.create_ticket("task", long_title, target="alpha")
    out = run_cli(monkeypatch, capsys, "--target", "alpha", "--query", "ENDMARKER")
    assert "ENDMARKER" in out             # would be clipped away at 60 chars


def test_query_all_projects(two_fake_projects, monkeypatch, capsys):
    ticket_db.create_ticket("task", "alpha noise", target="alpha")
    hit = ticket_db.create_ticket("task", "unique-zebra sighting", target="beta")["id"]
    out = run_cli(monkeypatch, capsys, "--all-projects", "--query", "unique-zebra",
                  "--json")
    assert hit in out
    assert json_block(out)["query"] == "unique-zebra"   # set on the merge path too


def test_query_json_carries_query_key(fake_projects, monkeypatch, capsys):
    ticket_db.create_ticket("task", "searchable", target="alpha")
    out = run_cli(monkeypatch, capsys, "--target", "alpha", "--query", "searchable",
                  "--json")
    data = json_block(out)
    assert data["query"] == "searchable"
    assert data["limit"] == 0             # query mode is unlimited by default


def test_nonquery_default_limit_still_50(fake_projects, monkeypatch, capsys):
    # Guards the --limit default=None sentinel refactor: without --query the
    # old default of 50 (and the banner) must be unchanged.
    for i in range(51):
        ticket_db.create_ticket("task", f"bulk {i}", target="alpha")
    out = run_cli(monkeypatch, capsys, "--target", "alpha")
    assert out.splitlines()[0].startswith("!! TRUNCATED: showing 50 of 51")


def test_title_newlines_collapsed(fake_projects, monkeypatch, capsys):
    ticket_db.create_ticket("task", "first line\nsecond line", target="alpha")
    out = run_cli(monkeypatch, capsys, "--target", "alpha")
    assert "first line second line" in out
