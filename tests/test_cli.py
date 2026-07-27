"""simplex CLI dispatcher contract (SIMP-D2-023): every mapped subcommand
reaches its module, --help exits 0, unknown commands exit 2, project use is
a pure git-checkout wrapper."""
import sys
import types

from simplex_cli import cli


def test_no_args_prints_usage(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "simplex ticket create" in out
    assert "simplex project use" in out


def test_every_mapped_subcommand_help_exits_0():
    for words, (module, _injected) in cli.COMMANDS.items():
        if module == "memory.session_digest":
            continue  # digest has no argparse — --help would run a real digest
        rc = cli.main(list(words) + ["--help"])
        assert rc == 0, f"--help failed for: {' '.join(words)}"


def test_unknown_command_exits_2(capsys):
    assert cli.main(["frobnicate"]) == 2
    assert "unknown command" in capsys.readouterr().err


def test_unknown_project_subcommand_exits_2(capsys):
    assert cli.main(["project", "destroy"]) == 2


def test_argv_restored_after_dispatch():
    before = list(sys.argv)
    cli.main(["status", "--help"])
    assert sys.argv == before


def test_injected_args_reach_module(monkeypatch):
    seen = {}
    fake = types.ModuleType("conversation.conversation_read")

    def fake_main():
        seen["argv"] = sys.argv[1:]
        return 0
    fake.main = fake_main
    monkeypatch.setitem(sys.modules, "conversation.conversation_read", fake)
    rc = cli.main(["history", "search", "--query", "x"])
    assert rc == 0
    assert seen["argv"] == ["--action", "search", "--query", "x"]


def test_project_use_checks_out_mapped_branch(fake_projects, monkeypatch, capsys):
    calls = {}

    def fake_run(cmd, cwd=None, **kw):
        calls["cmd"], calls["cwd"] = cmd, cwd
        return types.SimpleNamespace(returncode=0)
    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    rc = cli.main(["project", "use", "alpha"])
    assert rc == 0
    assert calls["cmd"] == ["git", "checkout", "alpha-branch"]
    assert calls["cwd"] == str(cli.REPO_ROOT)
    assert "OK active project: alpha" in capsys.readouterr().out


def test_project_use_unknown_project_exits_1(fake_projects, capsys):
    assert cli.main(["project", "use", "nope"]) == 1
    assert "not registered" in capsys.readouterr().err


def test_project_list_marks_active(fake_projects, on_branch, capsys):
    on_branch("alpha-branch")
    assert cli.main(["project", "list"]) == 0
    out = capsys.readouterr().out
    assert "* alpha" in out
    assert "simplex_mind" in out
