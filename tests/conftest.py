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
def mem_db(tmp_path, monkeypatch):
    """Point memory_db at a temp database file."""
    from memory import memory_db
    monkeypatch.setattr(memory_db, "DB_PATH", tmp_path / "memory.db")
    monkeypatch.setattr(memory_db, "_schema_ready", False)
    return memory_db
