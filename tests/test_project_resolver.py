import pytest

import project_resolver as pr


def test_load_projects_parses_fields(fake_projects):
    projects = pr.load_projects()
    assert set(projects) == {"alpha"}
    alpha = projects["alpha"]
    assert alpha["ticket_prefix"] == "ALPH"
    assert alpha["branch"] == "alpha-branch"
    assert alpha["path"] == str(fake_projects["proj_dir"])


def test_machine_id_uppercased(fake_projects):
    assert pr.get_machine_id() == "T9"


def test_active_project_from_branch(fake_projects, on_branch):
    on_branch("alpha-branch")
    assert pr.get_active_project()["name"] == "alpha"
    on_branch("master")
    # cache was set directly; re-set to master and expect no active project
    assert pr.get_active_project() is None


def test_get_all_projects_includes_implicit_simplex(fake_projects):
    names = {p["name"] for p in pr.get_all_projects()}
    assert names == {"alpha", "simplex_mind"}


def test_ticket_db_path_explicit_target(fake_projects):
    path = pr.get_ticket_db_path("alpha")
    assert path == fake_projects["proj_dir"] / "database" / "tickets.db"


def test_ticket_db_path_unknown_target_raises(fake_projects):
    with pytest.raises(ValueError, match="Unknown project target"):
        pr.get_ticket_db_path("nope")


def test_ticket_db_path_falls_back_to_brain(fake_projects, on_branch):
    on_branch("master")
    assert pr.get_ticket_db_path() == fake_projects["root"] / "database" / "tickets.db"


def test_prefix_resolution(fake_projects, on_branch):
    assert pr.get_ticket_prefix("alpha") == "ALPH"
    on_branch("master")
    assert pr.get_ticket_prefix() == "SIMP"


def test_infer_project_from_prefix(fake_projects):
    assert pr.infer_project_from_prefix("ALPH-T9-007") == "alpha"
    assert pr.infer_project_from_prefix("SIMP-T9-001") == "simplex_mind"
    assert pr.infer_project_from_prefix("ZZZZ-T9-001") is None
    assert pr.infer_project_from_prefix("noprefix") is None
