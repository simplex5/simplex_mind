"""
Tool: Doctor — health validation for the whole brain (SIMP-D2-021)
Purpose: One command that says whether this checkout is actually operational,
         instead of subsystems failing silently into healthy-looking emptiness.

Modes:
    python src/utils/agent_skills/doctor.py            # full validation, exit 1 if any check FAILs
    python src/utils/agent_skills/doctor.py --status   # compact status page, always exit 0
    python src/utils/agent_skills/doctor.py --json     # machine-readable results

Onboarding classification (the config.json untracking seam):
    onboarded    — config.json present with onboarding_complete: true
    fresh_clone  — no config AND no local state (projects.yaml, DBs) → follow SETUP.md
    lost_config  — no config but local state exists: an established machine pulled the
                   untracking migration → run init.py --mark-onboarded, do NOT re-onboard

Every check returns healthy/warn/fail plus a one-line remediation. Checks are
read-only (sqlite opened with mode=ro) and independent — one broken subsystem
never hides another.
"""

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

sys_path_entry = str(Path(__file__).parent)
if sys_path_entry not in sys.path:
    sys.path.insert(0, sys_path_entry)

try:
    from ._common import REPO_ROOT
except ImportError:
    from _common import REPO_ROOT

try:
    from . import project_resolver
except ImportError:
    import project_resolver

OK, WARN, FAIL = "ok", "warn", "fail"
HOUSE_IDENTITY = ("simplex5", "dev@simplex5.com")


def classify_onboarding(root: Path = REPO_ROOT) -> str:
    """'onboarded' | 'fresh_clone' | 'lost_config' — see module docstring."""
    config = root / "database" / "config.json"
    try:
        if json.loads(config.read_text(encoding="utf-8")).get("onboarding_complete") is True:
            return "onboarded"
    except (OSError, json.JSONDecodeError):
        pass
    state_markers = [
        root / "projects.yaml",
        root / "database" / "memory" / "memory.db",
        root / "database" / "tickets.db",
        root / "database" / "conversation_history.db",
    ]
    return "lost_config" if any(m.exists() for m in state_markers) else "fresh_clone"


def _result(name: str, level: str, detail: str, remedy: str = "") -> dict:
    return {"name": name, "level": level, "detail": detail, "remedy": remedy}


def _count_ro(db_path: Path, query: str):
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        return con.execute(query).fetchone()
    finally:
        con.close()


def _parsed_yaml(root: Path) -> dict:
    yaml_path = root / "projects.yaml"
    if not yaml_path.exists():
        return {}
    return project_resolver._parse_yaml(yaml_path.read_text(encoding="utf-8"))


def check_onboarding(root: Path) -> dict:
    state = classify_onboarding(root)
    if state == "onboarded":
        return _result("onboarding", OK, "complete")
    if state == "fresh_clone":
        return _result("onboarding", FAIL, "fresh clone detected — no config.json and no local state",
                       "follow the onboarding flow in SETUP.md")
    return _result("onboarding", FAIL, "config.json missing but databases exist (untracking migration)",
                   "run: python src/utils/agent_skills/init.py --mark-onboarded (do NOT re-run onboarding)")


def check_projects_yaml(root: Path) -> dict:
    yaml_path = root / "projects.yaml"
    if not yaml_path.exists():
        return _result("projects.yaml", FAIL, "missing",
                       "create projects.yaml per SETUP.md (local config, gitignored)")
    try:
        data = _parsed_yaml(root)
    except Exception as e:
        return _result("projects.yaml", FAIL, f"unparseable ({e})", "fix the YAML syntax")
    issues = []
    if not data.get("machine"):
        issues.append("top-level machine: key missing (ticket IDs need it)")
    for name, cfg in (data.get("projects") or {}).items():
        if not cfg.get("branch"):
            issues.append(f"project '{name}' has no branch:")
        path = cfg.get("path")
        if path and not Path(path).expanduser().exists():
            issues.append(f"project '{name}' path does not exist: {path}")
    if issues:
        return _result("projects.yaml", WARN, "; ".join(issues), "edit projects.yaml")
    n = len(data.get("projects") or {})
    return _result("projects.yaml", OK, f"{n} project(s), machine {data.get('machine')}")


def check_ticket_dbs(root: Path) -> dict:
    brain_db = root / "database" / "tickets.db"
    if not brain_db.exists():
        return _result("tickets", FAIL, "brain tickets.db missing",
                       "run: python src/utils/agent_skills/init.py")
    parts, issues = [], []
    try:
        (n_open,) = _count_ro(brain_db, "SELECT COUNT(*) FROM tickets WHERE status = 'open'")
        parts.append(f"brain: {n_open} open")
    except sqlite3.Error as e:
        issues.append(f"brain DB unreadable ({e})")
    for proj in project_resolver.get_all_projects():
        if proj["name"] == "simplex_mind":
            continue
        db = Path(proj["path"]) / "database" / "tickets.db"
        if not db.exists():
            issues.append(f"{proj['name']}: no tickets.db")
            continue
        try:
            (n_open,) = _count_ro(db, "SELECT COUNT(*) FROM tickets WHERE status = 'open'")
            parts.append(f"{proj['name']}: {n_open} open")
        except sqlite3.Error as e:
            issues.append(f"{proj['name']}: unreadable ({e})")
    if issues:
        return _result("tickets", FAIL, "; ".join(issues + parts),
                       "check project paths in projects.yaml; restore from simplex backup if corrupt")
    return _result("tickets", OK, "; ".join(parts))


def check_memory_db(root: Path) -> dict:
    db = root / "database" / "memory" / "memory.db"
    if not db.exists():
        return _result("memory", FAIL, "memory.db missing", "run: python src/utils/agent_skills/init.py")
    try:
        n, last = _count_ro(db, "SELECT COUNT(*), MAX(created_at) FROM memory_entries")
        return _result("memory", OK, f"{n} entries, last write {str(last)[:10] if last else 'never'}")
    except sqlite3.Error as e:
        return _result("memory", FAIL, f"unreadable ({e})", "restore from simplex backup")


def check_conversation_db(root: Path) -> dict:
    db = root / "database" / "conversation_history.db"
    if not db.exists():
        return _result("history", FAIL, "conversation_history.db missing",
                       "run: python src/utils/agent_skills/init.py")
    try:
        (n_sessions,) = _count_ro(db, "SELECT COUNT(*) FROM sessions")
        (n_messages,) = _count_ro(db, "SELECT COUNT(*) FROM messages")
        (fts,) = _count_ro(db, "SELECT COUNT(*) FROM sqlite_master WHERE name = 'messages_fts'")
        if not fts:
            return _result("history", FAIL, "messages_fts table missing (search broken)",
                           "recreate the DB via init.py, then re-ingest with --force")
        return _result("history", OK, f"{n_sessions} sessions, {n_messages} messages")
    except sqlite3.Error as e:
        return _result("history", FAIL, f"unreadable ({e})", "restore from simplex backup")


def check_subconscious(root: Path) -> dict:
    index = root / "database" / "memory" / "subconscious_index.json"
    pieces = root / "subconscious"
    if not index.exists():
        if pieces.exists() and any(pieces.glob("*.md")):
            return _result("subconscious", FAIL, "index not built",
                           "run: python src/utils/agent_skills/subconscious/subconscious_index.py")
        return _result("subconscious", OK, "no pieces (nothing to index)")
    try:
        from memory.session_digest import _check_subconscious_index_staleness
        stale = _check_subconscious_index_staleness()
    except Exception as e:
        return _result("subconscious", WARN, f"staleness check failed ({e})", "run doctor from the repo root")
    if stale:
        return _result("subconscious", WARN, "index stale — pieces/keywords edited after last build",
                       "run: python src/utils/agent_skills/subconscious/subconscious_index.py")
    return _result("subconscious", OK, "index built and fresh")


def check_autotune(root: Path) -> dict:
    state_path = root / "database" / "memory" / "subconscious_autotune_state.json"
    if not state_path.exists():
        return _result("autotune", WARN, "never run (expected before the first weekly cron run)",
                       "run subconscious_autotune.py manually or wait for cron")
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return _result("autotune", FAIL, f"state file unreadable ({e})",
                       "delete it and re-run subconscious_autotune.py")
    err = state.get("last_run_error")
    if err:
        return _result("autotune", FAIL, f"last cron run failed: {err.get('error', 'unknown')}",
                       "check logs/subconscious_autotune.log")
    pending = len(state.get("pending", []))
    detail = f"last run {str(state.get('last_run', 'unknown'))[:10]}"
    if pending:
        detail += f", {pending} candidates pending review"
    return _result("autotune", OK, detail)


def check_venv(root: Path) -> dict:
    if not (root / "venv").is_dir():
        return _result("venv", WARN, "no venv directory",
                       "python3 -m venv venv && venv/bin/pip install -r requirements.txt -e .")
    try:
        from memory.session_digest import _check_venv_drift
        issues = _check_venv_drift()
    except Exception as e:
        return _result("venv", WARN, f"drift check failed ({e})", "run doctor from the repo root")
    if issues:
        return _result("venv", WARN, "; ".join(issues), "pip install -r requirements.txt")
    return _result("venv", OK, "deps match requirements.txt pins")


def check_hooks(root: Path) -> dict:
    settings = root / ".claude" / "settings.json"
    if not settings.exists():
        return _result("hooks", FAIL, ".claude/settings.json missing", "restore it from git")
    try:
        blob = json.dumps(json.loads(settings.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as e:
        return _result("hooks", FAIL, f"settings.json unparseable ({e})", "restore it from git")
    required = ["session_digest.py", "subconscious_recall.py", "protocol_gate.py", "conversation_ingest.py"]
    missing = [name for name in required if name not in blob]
    if missing:
        return _result("hooks", FAIL, f"not registered: {', '.join(missing)}", "restore .claude/settings.json from git")
    return _result("hooks", OK, "digest, recall, gate, ingest registered")


def check_git_identity(root: Path) -> dict:
    def _config(key):
        try:
            r = subprocess.run(["git", "-C", str(root), "config", key],
                               capture_output=True, text=True, timeout=5)
            return r.stdout.strip()
        except Exception:
            return ""
    name, email = _config("user.name"), _config("user.email")
    if not name or not email:
        return _result("git identity", FAIL, "user.name/user.email unset (commits will fail attribution)",
                       f"git config user.name {HOUSE_IDENTITY[0]} && git config user.email {HOUSE_IDENTITY[1]}")
    if (name, email) != HOUSE_IDENTITY:
        return _result("git identity", WARN, f"{name} <{email}> (house convention is "
                       f"{HOUSE_IDENTITY[0]} <{HOUSE_IDENTITY[1]}> — ignore if this is your own fork)")
    return _result("git identity", OK, f"{name} <{email}>")


def check_branch_mapping(root: Path) -> dict:
    try:
        r = subprocess.run(["git", "-C", str(root), "branch", "--show-current"],
                           capture_output=True, text=True, timeout=5)
        branch = r.stdout.strip()
    except Exception:
        branch = ""
    if not branch:
        return _result("branch", WARN, "cannot determine current branch", "run doctor inside the git repo")
    if branch in ("master", "main", "develop"):
        return _result("branch", OK, f"{branch} — no active project (brain/SIMP mode)")
    for name, cfg in (_parsed_yaml(root).get("projects") or {}).items():
        if cfg.get("branch") == branch:
            return _result("branch", OK, f"{branch} — active project: {name}")
    return _result("branch", WARN, f"{branch} is not mapped to any project in projects.yaml",
                   "add a projects.yaml entry or checkout a mapped branch (simplex project use <name>)")


CHECKS = [
    check_onboarding,
    check_projects_yaml,
    check_ticket_dbs,
    check_memory_db,
    check_conversation_db,
    check_subconscious,
    check_autotune,
    check_venv,
    check_hooks,
    check_git_identity,
    check_branch_mapping,
]


def run_checks(root: Path = REPO_ROOT) -> list:
    results = []
    for check in CHECKS:
        try:
            results.append(check(root))
        except Exception as e:  # a crashing check is itself a finding, never a silent skip
            results.append(_result(check.__name__.replace("check_", ""), FAIL,
                                   f"check crashed ({type(e).__name__}: {e})", "report this as a doctor bug"))
    return results


LABELS = {OK: "[ OK ]", WARN: "[WARN]", FAIL: "[FAIL]"}


def main() -> int:
    parser = argparse.ArgumentParser(description="simplex_mind health checks")
    parser.add_argument("--status", action="store_true", help="compact status page, always exit 0")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args()

    results = run_checks(args.root)
    fails = [r for r in results if r["level"] == FAIL]
    warns = [r for r in results if r["level"] == WARN]

    if args.json:
        print(json.dumps({"healthy": not fails, "results": results}, indent=2))
        return 0 if args.status or not fails else 1

    if args.status:
        print(f"simplex_mind status — {len(results)} subsystems, "
              f"{len(fails)} failed, {len(warns)} warnings")
        for r in results:
            print(f"  {r['name']}: {r['level'].upper()} — {r['detail']}")
        return 0

    print(f"simplex_mind doctor — {len(results)} checks")
    for r in results:
        print(f"{LABELS[r['level']]} {r['name']}: {r['detail']}")
        if r["remedy"] and r["level"] != OK:
            print(f"       -> {r['remedy']}")
    if fails:
        print(f"\nRESULT: DEGRADED — {len(fails)} check(s) failed, {len(warns)} warning(s)")
        return 1
    if warns:
        print(f"\nRESULT: HEALTHY with {len(warns)} warning(s)")
    else:
        print("\nRESULT: HEALTHY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
