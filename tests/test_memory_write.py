"""memory_write auto-tags DB entries with the active project (SIMP-D2-022)."""
from memory import memory_write


def test_active_project_tag_appended(fake_projects, on_branch):
    on_branch("alpha-branch")
    assert memory_write._with_project_tag(["x"]) == ["x", "project:alpha"]


def test_tag_not_duplicated(fake_projects, on_branch):
    on_branch("alpha-branch")
    assert memory_write._with_project_tag(["project:alpha"]) == ["project:alpha"]


def test_no_active_project_leaves_tags_alone(fake_projects, on_branch):
    on_branch("master")
    assert memory_write._with_project_tag(["x"]) == ["x"]
    assert memory_write._with_project_tag(None) is None
