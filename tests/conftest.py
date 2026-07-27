"""Shared fixtures: isolate every test from the real projects.yaml, git branch,
and live databases. No test may touch database/ or the user's projects."""
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src" / "utils" / "agent_skills"))

import project_resolver  # noqa: E402


@pytest.fixture
def fake_projects(tmp_path, monkeypatch):
    """Point project_resolver at a temp projects.yaml with one project (+ machine id)
    and a temp 'repo root' so the brain-DB fallback lands in tmp too."""
    proj_dir = tmp_path / "proj_alpha"
    (proj_dir / "database").mkdir(parents=True)
    yaml_path = tmp_path / "projects.yaml"
    yaml_path.write_text(textwrap.dedent(f"""\
        machine: T9
        projects:
          alpha:
            path: {proj_dir}
            ref_file: CLAUDE.md.ref
            ticket_prefix: ALPH
            branch: alpha-branch
    """))
    monkeypatch.setattr(project_resolver, "_PROJECTS_YAML", yaml_path)
    monkeypatch.setattr(project_resolver, "_REPO_ROOT", tmp_path)
    # Reset process-lifetime caches
    monkeypatch.setattr(project_resolver, "_projects_cache", None)
    monkeypatch.setattr(project_resolver, "_machine_cache", ...)
    monkeypatch.setattr(project_resolver, "_branch_cache", ...)
    return {"root": tmp_path, "proj_dir": proj_dir, "yaml": yaml_path}


@pytest.fixture
def on_branch(monkeypatch):
    """Force the resolver's view of the current git branch."""
    def _set(branch):
        monkeypatch.setattr(project_resolver, "_branch_cache", branch)
    return _set


@pytest.fixture
def fake_repo(tmp_path):
    """Build a temp brain-repo root with selectable state, for doctor/digest
    tests. Returns a builder: fake_repo(config=..., dbs=..., projects_yaml=...)."""
    import sqlite3

    def _build(config=None, dbs=(), projects_yaml=False):
        root = tmp_path / "brain"
        (root / "database" / "memory").mkdir(parents=True, exist_ok=True)
        if config is not None:
            (root / "database" / "config.json").write_text(
                __import__("json").dumps(config), encoding="utf-8")
        for db in dbs:  # relative paths like "database/memory/memory.db"
            path = root / db
            path.parent.mkdir(parents=True, exist_ok=True)
            sqlite3.connect(path).close()  # valid empty sqlite file
        if projects_yaml:
            (root / "projects.yaml").write_text("machine: T9\nprojects:\n", encoding="utf-8")
        return root

    return _build


@pytest.fixture
def mem_db(tmp_path, monkeypatch):
    """Point memory_db at a temp database file."""
    from memory import memory_db
    monkeypatch.setattr(memory_db, "DB_PATH", tmp_path / "memory.db")
    monkeypatch.setattr(memory_db, "_schema_ready", False)
    return memory_db
