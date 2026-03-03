#!/usr/bin/env python3
"""
git_commit.py — Git operations for project framework files.

Subcommands:
  init      git init + stage framework files + initial commit
  status    Parsed git status --porcelain
  commit    Stage framework files (or --paths) + commit
  diff      git diff --stat summary

Usage:
    python src/utils/claude_code_skills/git_commit.py init
    python src/utils/claude_code_skills/git_commit.py status
    python src/utils/claude_code_skills/git_commit.py commit -m "add new tool"
    python src/utils/claude_code_skills/git_commit.py commit -m "fix parser" --paths src/utils/parser.py
    python src/utils/claude_code_skills/git_commit.py diff
"""

import argparse
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Directories that are framework source
FRAMEWORK_DIRS = [
    "src/",
    "goals/",
    "args/",
]

# Individual root files that are framework source
FRAMEWORK_FILES = [
    "CLAUDE.md",
    "CLAUDE.md.ref",
    "requirements.txt",
    "requirements.base.txt",
    ".gitignore",
    "README.md",
    "database/memory/MEMORY.md",
    "database/config.json",
]


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command from the project root."""
    return subprocess.run(
        cmd, cwd=_PROJECT_ROOT, capture_output=True, text=True, check=check
    )


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return _run(["git", *args], check=check)


def _collect_framework_paths() -> list[str]:
    """Return list of existing framework paths to stage."""
    paths = []
    for d in FRAMEWORK_DIRS:
        full = _PROJECT_ROOT / d
        if full.is_dir():
            paths.append(d)
    for f in FRAMEWORK_FILES:
        full = _PROJECT_ROOT / f
        if full.is_file():
            paths.append(f)
    return paths


def cmd_init(_args: argparse.Namespace) -> None:
    """Initialize git repo and create initial commit."""
    git_dir = _PROJECT_ROOT / ".git"
    if git_dir.exists():
        print("[git_commit] .git/ already exists — skipping init")
    else:
        _git("init")
        print("[git_commit] Initialized git repository")

    # Stage framework files
    paths = _collect_framework_paths()
    if not paths:
        print("[git_commit] No framework files found to stage", file=sys.stderr)
        sys.exit(1)

    _git("add", *paths)
    print(f"[git_commit] Staged {len(paths)} framework paths")

    # Initial commit
    result = _git("commit", "-m", "initial commit: simplex_mind framework", check=False)
    if result.returncode == 0:
        print("[git_commit] Created initial commit")
    else:
        # Could be "nothing to commit" if already committed
        print(f"[git_commit] {result.stdout.strip() or result.stderr.strip()}")


def cmd_status(_args: argparse.Namespace) -> None:
    """Show parsed git status."""
    result = _git("status", "--porcelain", check=False)
    if result.returncode != 0:
        print(f"[git_commit] Error: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    lines = result.stdout.strip()
    if not lines:
        print("[git_commit] Working tree clean")
        return

    for line in lines.splitlines():
        status_code = line[:2]
        filepath = line[3:]
        labels = {
            "M ": "staged",
            " M": "modified",
            "MM": "staged+modified",
            "A ": "added",
            "??": "untracked",
            " D": "deleted",
            "D ": "deleted(staged)",
            "R ": "renamed",
        }
        label = labels.get(status_code, status_code.strip())
        print(f"  {label:18s} {filepath}")


def cmd_commit(args: argparse.Namespace) -> None:
    """Stage and commit framework files."""
    if not args.message:
        print("[git_commit] Error: -m message required", file=sys.stderr)
        sys.exit(1)

    if args.paths:
        # Stage only specified paths
        paths = args.paths
    else:
        # Stage all framework paths
        paths = _collect_framework_paths()

    if not paths:
        print("[git_commit] No files to stage", file=sys.stderr)
        sys.exit(1)

    _git("add", *paths)

    result = _git("commit", "-m", args.message, check=False)
    if result.returncode == 0:
        # Extract short summary from git output
        first_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        print(f"[git_commit] Committed: {first_line}")
    else:
        msg = result.stdout.strip() or result.stderr.strip()
        if "nothing to commit" in msg:
            print("[git_commit] Nothing to commit — working tree clean")
        else:
            print(f"[git_commit] Commit failed: {msg}", file=sys.stderr)
            sys.exit(1)


def cmd_diff(_args: argparse.Namespace) -> None:
    """Show diff stat summary."""
    # Show both staged and unstaged
    result = _git("diff", "--stat", "HEAD", check=False)
    output = result.stdout.strip()

    if not output:
        # Try without HEAD (for initial state before any commit)
        result = _git("diff", "--stat", check=False)
        output = result.stdout.strip()

    if output:
        print(output)
    else:
        print("[git_commit] No changes")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Git operations for project framework files."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialize git repo with framework files")
    sub.add_parser("status", help="Show parsed git status")

    commit_p = sub.add_parser("commit", help="Stage and commit framework files")
    commit_p.add_argument("-m", "--message", required=True, help="Commit message")
    commit_p.add_argument(
        "--paths", nargs="+", help="Specific paths to stage (default: all framework files)"
    )

    sub.add_parser("diff", help="Show diff stat summary")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "status": cmd_status,
        "commit": cmd_commit,
        "diff": cmd_diff,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
