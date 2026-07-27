"""simplex — unified CLI dispatcher (SIMP-D2-023).

Thin by design: every subcommand rewrites argv and calls the existing
agent-skills module's main(), so flags and --help come from the modules
themselves and no tool logic lives here. Script paths remain canonical
(hooks, cron, non-Claude agents call them directly); the CLI is an installed
convenience. Supported install is editable only (`pip install -e .`) — the
dispatcher resolves the agent-skills tree relative to this file inside the
repo checkout.

`simplex project use <name>` is deliberately just a `git checkout` of the
project's branch: the branch IS the active-project selector (no state to
drift), this command only saves the projects.yaml lookup.
"""
import importlib
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS = REPO_ROOT / "src" / "utils" / "agent_skills"

# (command words) -> (agent-skills module, injected argv prefix)
COMMANDS = {
    ("init",): ("init", []),
    ("doctor",): ("doctor", []),
    ("status",): ("doctor", ["--status"]),
    ("digest",): ("memory.session_digest", []),
    ("ticket", "create"): ("tickets.ticket_create", []),
    ("ticket", "list"): ("tickets.ticket_list", []),
    ("ticket", "read"): ("tickets.ticket_read", []),
    ("ticket", "update"): ("tickets.ticket_update", []),
    ("memory", "write"): ("memory.memory_write", []),
    ("memory", "search"): ("memory.hybrid_search", []),
    ("memory", "read"): ("memory.memory_read", []),
    ("memory", "sync"): ("memory.memory_sync", []),
    ("history", "ingest"): ("conversation.conversation_ingest", []),
    ("history", "search"): ("conversation.conversation_read", ["--action", "search"]),
    ("history", "stats"): ("conversation.conversation_read", ["--action", "stats"]),
}


def _print_usage(file=None):
    file = file or sys.stdout
    print("simplex — simplex_mind brain CLI\n", file=file)
    print("  simplex project use <name>   checkout the project's branch (= activate it)", file=file)
    print("  simplex project list         registered projects, active one starred", file=file)
    for words in sorted(COMMANDS):
        print(f"  simplex {' '.join(words)}", file=file)
    print("\nEvery subcommand forwards to the corresponding agent-skills tool —", file=file)
    print("append --help for its flags (e.g. simplex ticket create --help).", file=file)


def _ensure_skills_path():
    # The tools' import fallbacks assume script-mode sys.path (their own dir
    # present) — recreate that environment for package-mode dispatch too.
    for d in (SKILLS, SKILLS / "memory", SKILLS / "tickets", SKILLS / "conversation"):
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))


def _dispatch(module_name: str, args: list, label: str) -> int:
    _ensure_skills_path()
    mod = importlib.import_module(module_name)
    saved_argv = sys.argv
    sys.argv = [f"simplex {label}"] + args
    try:
        rc = mod.main()
    except SystemExit as e:
        code = e.code
        return code if isinstance(code, int) else (0 if code is None else 1)
    finally:
        sys.argv = saved_argv
    return rc if isinstance(rc, int) else 0


def _project_use(args: list) -> int:
    if not args:
        print("usage: simplex project use <name>", file=sys.stderr)
        return 2
    _ensure_skills_path()
    import project_resolver
    name = args[0]
    proj = project_resolver.get_project(name)
    if not proj:
        print(f"ERROR unknown project '{name}' — not registered in projects.yaml", file=sys.stderr)
        return 1
    branch = proj.get("branch")
    if not branch:
        print(f"ERROR project '{name}' has no branch: in projects.yaml", file=sys.stderr)
        return 1
    result = subprocess.run(["git", "checkout", branch], cwd=str(REPO_ROOT))
    if result.returncode != 0:
        return result.returncode
    print(f"OK active project: {name} (branch {branch})")
    return 0


def _project_list() -> int:
    _ensure_skills_path()
    import project_resolver
    active = project_resolver.get_active_project()
    active_name = active["name"] if active else None
    for proj in project_resolver.get_all_projects():
        marker = "*" if proj["name"] == active_name else " "
        print(f"{marker} {proj['name']}  (branch {proj.get('branch') or '-'}, "
              f"prefix {proj['ticket_prefix']})")
    return 0


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not SKILLS.is_dir():
        print("ERROR simplex requires an editable install from the simplex_mind repo: "
              "pip install -e .", file=sys.stderr)
        return 1
    if not args or args[0] in ("-h", "--help"):
        _print_usage()
        return 0
    if args[0] == "project":
        sub = args[1] if len(args) > 1 else ""
        if sub == "use":
            return _project_use(args[2:])
        if sub == "list":
            return _project_list()
        print(f"ERROR unknown command: project {sub}".rstrip(), file=sys.stderr)
        _print_usage(file=sys.stderr)
        return 2
    for length in (2, 1):  # longest prefix wins
        key = tuple(args[:length])
        if key in COMMANDS:
            module_name, injected = COMMANDS[key]
            return _dispatch(module_name, injected + args[length:], " ".join(key))
    print(f"ERROR unknown command: {' '.join(args[:2])}", file=sys.stderr)
    _print_usage(file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
