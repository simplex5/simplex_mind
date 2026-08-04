"""Push guard PreToolUse hook contract (SIMP-D2-053): DENIES agent-driven
`git push` of any simplex_mind branch outside {master, develop} — the family's
first denying hook. Zero ask rows: every ambiguity after a brain-push is
established denies, with a hand-run remediation in the message. Project-repo
pushes and non-push commands stay silent; the guard fails open on its own
errors (degraded marker, no decision)."""
import io
import json
import sqlite3
import sys
from types import SimpleNamespace

import pytest

import push_guard
from memory import hook_state


# ---------------------------------------------------------------- pure parser

def test_split_segments_operators_newlines_and_quotes():
    assert push_guard.split_segments("a && b; c | d\ne") == ["a", "b", "c", "d", "e"]
    # quoted operators do not split
    segs = push_guard.split_segments('echo "a && b; c" && git status')
    assert segs == ['echo "a && b; c"', "git status"]


def test_effective_dirs_tracks_cd_and_powershell_synonyms(tmp_path):
    segs = push_guard.split_segments("cd /proj && git push; Set-Location /other; git push")
    pairs = push_guard.effective_dirs(segs, str(tmp_path))
    assert pairs[0] == ("cd /proj", str(tmp_path))
    assert pairs[1][1].replace("\\", "/").endswith("/proj")
    assert pairs[3][1].replace("\\", "/").endswith("/other")


def test_parse_push_ignores_non_push_commands():
    assert push_guard.parse_push("git status") is None
    assert push_guard.parse_push("echo git push") is None  # 'git' not command head after echo... still parsed?
    assert push_guard.parse_push("ls -la") is None


def test_parse_push_finds_push_mid_segment():
    parsed = push_guard.parse_push("if ($?) { git push origin animal-town }")
    assert parsed is not None
    assert parsed.remote == "origin"
    assert "animal-town" in parsed.refspecs


def test_parse_push_consumes_arg_taking_flags():
    parsed = push_guard.parse_push("git push -o ci.skip origin master")
    assert parsed.remote == "origin" and parsed.refspecs == ["master"]
    parsed = push_guard.parse_push("git push --push-option=ci.skip origin master")
    assert parsed.remote == "origin" and parsed.refspecs == ["master"]


def test_parse_push_unknown_double_dash_flag_marks_ambiguity():
    parsed = push_guard.parse_push("git push --weird-flag value origin animal-town")
    assert parsed.ambiguous


def test_parse_push_extracts_c_path_and_modes():
    parsed = push_guard.parse_push("git -C /somewhere push --mirror")
    assert parsed.c_path == "/somewhere" and parsed.mirror
    parsed = push_guard.parse_push("git push --delete origin topic")
    assert parsed.delete and parsed.refspecs == ["topic"]
    parsed = push_guard.parse_push("git push --tags origin")
    assert parsed.tags and not parsed.refspecs


# ------------------------------------------------------------ integration env

@pytest.fixture
def guard_env(tmp_path, monkeypatch):
    """Temp brain root + temp hooks.db + fake current-branch lookup."""
    brain = tmp_path / "brainroot"
    (brain / "sub").mkdir(parents=True)
    project = tmp_path / "project_repo"
    project.mkdir()
    monkeypatch.setattr(push_guard, "_REPO_ROOT", brain)
    monkeypatch.setattr(hook_state, "DB_PATH", tmp_path / "hooks.db")

    branch_box = {"value": "animal-town"}
    monkeypatch.setattr(push_guard, "_current_branch", lambda d: branch_box["value"])

    def run(command, session_id="s1", tool_name="Bash", cwd=None, raw=None):
        payload = raw if raw is not None else json.dumps({
            "session_id": session_id,
            "tool_name": tool_name,
            "tool_input": {"command": command},
            "cwd": str(cwd or brain),
        }).encode()
        monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(payload)))
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = push_guard.main()
        out = buf.getvalue().strip()
        return rc, (json.loads(out) if out else None)

    return SimpleNamespace(run=run, brain=brain, project=project, tmp=tmp_path,
                           branch=branch_box)


def _events(tmp):
    con = sqlite3.connect(tmp / "hooks.db")
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT outcome, reason FROM hook_events WHERE hook='push_guard'").fetchall()
    con.close()
    return [(r["outcome"], r["reason"]) for r in rows]


def _is_deny(out):
    return (out is not None
            and out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny")


# ------------------------------------------------------------------ deny rows

def test_deny_explicit_project_branch(guard_env):
    rc, out = guard_env.run("git push origin animal-town")
    assert rc == 0 and _is_deny(out)
    assert "[push-guard: denied" in out["systemMessage"]
    assert "run it yourself in a terminal" in out["hookSpecificOutput"]["permissionDecisionReason"]
    assert ("fired", "ref-not-allowed") in _events(guard_env.tmp)


def test_deny_bare_push_on_project_branch(guard_env):
    rc, out = guard_env.run("git push")
    assert _is_deny(out)


def test_deny_head_push_on_project_branch(guard_env):
    rc, out = guard_env.run("git push origin HEAD")
    assert _is_deny(out)


def test_deny_cross_publish_src_outside_set(guard_env):
    rc, out = guard_env.run("git push origin animal-town:develop")
    assert _is_deny(out)


def test_deny_delete_protected(guard_env):
    for cmd in ("git push --delete origin master",
                "git push origin :develop",
                "git push --delete origin main"):
        rc, out = guard_env.run(cmd)
        assert _is_deny(out), cmd


def test_deny_force_to_protected(guard_env):
    guard_env.branch["value"] = "develop"
    rc, out = guard_env.run("git push --force origin develop")
    assert _is_deny(out)
    rc, out = guard_env.run("git push origin +develop")
    assert _is_deny(out)


def test_deny_all_and_mirror(guard_env):
    for cmd in ("git push --all origin", "git push --mirror origin"):
        rc, out = guard_env.run(cmd)
        assert _is_deny(out), cmd


def test_deny_second_remote_and_url(guard_env):
    for cmd in ("git push upstream master",
                "git push git@github.com:x/y.git master"):
        rc, out = guard_env.run(cmd)
        assert _is_deny(out), cmd
        assert ("fired", "remote-not-origin") in _events(guard_env.tmp)


def test_deny_unresolvable_branch(guard_env):
    guard_env.branch["value"] = None
    rc, out = guard_env.run("git push")
    assert _is_deny(out)
    assert ("fired", "branch-unresolvable") in _events(guard_env.tmp)


def test_deny_parse_ambiguity(guard_env):
    rc, out = guard_env.run("git push --weird-flag value origin animal-town")
    assert _is_deny(out)
    assert ("fired", "parse-ambiguity") in _events(guard_env.tmp)


def test_deny_git_c_into_brain_from_outside(guard_env):
    rc, out = guard_env.run(f'git -C "{guard_env.brain}" push origin animal-town',
                            cwd=guard_env.tmp)
    assert _is_deny(out)


def test_deny_mid_segment_powershell(guard_env):
    rc, out = guard_env.run("if ($?) { git push origin animal-town }",
                            tool_name="PowerShell")
    assert _is_deny(out)


def test_deny_newline_separated(guard_env):
    rc, out = guard_env.run("echo hi\ngit push origin animal-town")
    assert _is_deny(out)


def test_tag_by_name_denies_documented_false_positive(guard_env):
    rc, out = guard_env.run("git push origin v1.2.0")
    assert _is_deny(out)


# ----------------------------------------------------------------- allow rows

def test_allow_master_develop_refs(guard_env):
    for cmd in ("git push origin master", "git push origin develop",
                "git push origin master develop",
                "git push origin master:refs/heads/master",
                "git push origin develop:develop"):
        rc, out = guard_env.run(cmd)
        assert rc == 0 and out is None, cmd


def test_allow_bare_push_on_master(guard_env):
    guard_env.branch["value"] = "master"
    rc, out = guard_env.run("git push")
    assert out is None
    rc, out = guard_env.run("git push origin HEAD")
    assert out is None


def test_allow_project_repo_push(guard_env):
    rc, out = guard_env.run("git push origin any-branch", cwd=guard_env.project)
    assert out is None
    assert ("skipped", "outside-brain") in _events(guard_env.tmp)


def test_allow_cd_project_chain_from_brain(guard_env):
    rc, out = guard_env.run(f'cd "{guard_env.project}" && git push origin main')
    assert out is None


def test_allow_git_c_project_from_brain(guard_env):
    rc, out = guard_env.run(f'git -C "{guard_env.project}" push origin main')
    assert out is None


def test_allow_subdir_of_brain_still_guarded(guard_env):
    rc, out = guard_env.run("git push origin animal-town", cwd=guard_env.brain / "sub")
    assert _is_deny(out)


def test_allow_tags_only(guard_env):
    rc, out = guard_env.run("git push --tags origin")
    assert out is None


def test_allow_delete_unprotected_with_marker(guard_env):
    rc, out = guard_env.run("git push --delete origin develop-hermes-influence")
    assert rc == 0 and out is not None
    assert "permissionDecision" not in json.dumps(out)
    assert "[push-guard: allowed delete" in out["systemMessage"]
    assert ("allowed-delete", "remediation-path") in _events(guard_env.tmp)


def test_non_push_and_ungated_tool_silent(guard_env):
    rc, out = guard_env.run("git status && ls")
    assert out is None
    rc, out = guard_env.run("git push origin animal-town", tool_name="Edit")
    assert out is None
    assert ("skipped", "ungated-tool") in _events(guard_env.tmp)


# -------------------------------------------------------------- failure modes

def test_malformed_stdin_fails_open(guard_env):
    rc, out = guard_env.run(None, raw=b"total garbage")
    assert rc == 0 and out is None


def test_guard_crash_degrades_visibly_without_decision(guard_env, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("splat")
    monkeypatch.setattr(push_guard, "split_segments", boom)
    rc, out = guard_env.run("git push origin animal-town")
    assert rc == 0
    assert "[push-guard degraded:" in out["systemMessage"]
    assert "permissionDecision" not in json.dumps(out)
    assert ("degraded", "RuntimeError") in _events(guard_env.tmp)


def test_dry_run_treated_identically(guard_env):
    rc, out = guard_env.run("git push --dry-run origin animal-town")
    assert _is_deny(out)


# ------------------------------------------------------------------ doctor

def test_doctor_requires_push_guard_registration(tmp_path):
    import doctor
    root = tmp_path / "root"
    (root / ".claude").mkdir(parents=True)
    hooks = {"hooks": {"PreToolUse": [{"hooks": [
        {"command": "... session_digest.py ..."}, {"command": "... subconscious_recall.py ..."},
        {"command": "... protocol_gate.py ..."}, {"command": "... conversation_ingest.py ..."},
        {"command": "... pretooluse_gate.py ..."}]}]}}
    (root / ".claude" / "settings.json").write_text(json.dumps(hooks), encoding="utf-8")
    result = doctor.check_hooks(root)
    assert result["level"] == doctor.FAIL and "push_guard.py" in result["detail"]

    hooks["hooks"]["PreToolUse"][0]["hooks"].append({"command": "... push_guard.py ..."})
    (root / ".claude" / "settings.json").write_text(json.dumps(hooks), encoding="utf-8")
    result = doctor.check_hooks(root)
    assert result["level"] == doctor.OK and "push-guard" in result["detail"]
