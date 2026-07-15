"""
Tool: Project Resolver
Purpose: Shared utility for resolving project config from projects.yaml.
         Used by ticket system, memory tools, and session digest to route
         operations to the correct per-project database.

Functions:
    load_projects()              -> dict of project configs
    get_active_project()         -> config for project whose branch matches
                                    the current simplex_mind git branch, or None
    get_project(name)            -> config for a specific project
    get_ticket_db_path(target)   -> Path to <project_path>/database/tickets.db
    get_all_projects()           -> list of all project configs
    get_machine_id()             -> this machine's ticket-ID segment (e.g. "L1")
                                    from the top-level `machine:` key
    infer_project_from_prefix(ticket_id) -> project name matching the prefix

The active project is derived from the current simplex_mind git branch, by
matching against each project's `branch:` field in projects.yaml. On master,
no project is active.

Resolution order for ticket DB:
    1. Explicit target (project name)
    2. Prefix inference from ticket ID
    3. Active project (current git branch)
    4. Fallback: simplex_mind brain DB (prefix SIMP)
"""

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROJECTS_YAML = _REPO_ROOT / "projects.yaml"

# simplex_mind is always implicitly a project (brain tickets)
_SIMPLEX_MIND_ENTRY = {
    "name": "simplex_mind",
    "path": str(_REPO_ROOT),
    "ticket_prefix": "SIMP",
    "ref_file": None,
    "branch": "master",
}


def _parse_yaml(text: str) -> dict:
    """Parse projects.yaml. Uses PyYAML if available, otherwise minimal parser."""
    if yaml:
        return yaml.safe_load(text) or {}

    # Minimal fallback parser for the simple projects.yaml structure
    projects = {}
    top_level = {}
    current_project = None
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith("    ") and ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip("'\"")
            if current_project and key in ("path", "ref_file", "ticket_prefix", "branch"):
                projects[current_project][key] = value
        elif line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            current_project = stripped[:-1].strip()
            projects[current_project] = {}
        elif not line.startswith(" ") and ":" in stripped and not stripped.endswith(":"):
            key, _, value = stripped.partition(":")
            top_level[key.strip()] = value.split("#", 1)[0].strip().strip("'\"")

    top_level["projects"] = projects
    return top_level


# Process-lifetime caches. CLI tools are one-shot processes, so staleness
# is bounded to a single invocation; long-lived callers can pass refresh=True.
_projects_cache: Optional[Dict[str, Dict[str, Any]]] = None
_branch_cache: Any = ...  # Ellipsis = "not yet resolved" (None is a valid result)


def load_projects(refresh: bool = False) -> Dict[str, Dict[str, Any]]:
    """Parse projects.yaml and return dict of {name: config}. Cached per process."""
    global _projects_cache
    if _projects_cache is not None and not refresh:
        return _projects_cache

    if not _PROJECTS_YAML.exists():
        _projects_cache = {}
        return _projects_cache
    text = _PROJECTS_YAML.read_text(encoding="utf-8")
    data = _parse_yaml(text)
    raw = data.get("projects", {})

    result = {}
    for name, cfg in raw.items():
        path_str = cfg.get("path", "")
        result[name] = {
            "name": name,
            "path": str(Path(path_str).expanduser()),
            "ticket_prefix": cfg.get("ticket_prefix", name.upper()[:4]),
            "ref_file": cfg.get("ref_file"),
            "branch": cfg.get("branch"),
        }
    _projects_cache = result
    return result


_machine_cache: Any = ...  # Ellipsis = "not yet resolved" (None is a valid result)


def get_machine_id(refresh: bool = False) -> Optional[str]:
    """Return this machine's ticket-ID segment (e.g. "L1") from the top-level
    `machine:` key in projects.yaml, or None if unset. Per-machine local
    config — this is what keeps ticket IDs unique across machines."""
    global _machine_cache
    if _machine_cache is not ... and not refresh:
        return _machine_cache

    machine = None
    if _PROJECTS_YAML.exists():
        data = _parse_yaml(_PROJECTS_YAML.read_text(encoding="utf-8"))
        raw = data.get("machine")
        if raw:
            machine = str(raw).strip().upper() or None
    _machine_cache = machine
    return machine


def get_subconscious_source() -> Optional[Dict[str, Any]]:
    """Return the project config that hosts the subconscious library (its
    `subconscious/` directory of philosophy pieces), from the top-level
    `subconscious:` key in projects.yaml. None if unset — the subconscious
    engine is a no-op without it."""
    if not _PROJECTS_YAML.exists():
        return None
    data = _parse_yaml(_PROJECTS_YAML.read_text(encoding="utf-8"))
    name = data.get("subconscious")
    if not name:
        return None
    return get_project(str(name).strip())


def get_all_projects() -> List[Dict[str, Any]]:
    """Return all registered projects including implicit simplex_mind entry."""
    projects = load_projects()
    result = list(projects.values())
    # Add simplex_mind if not explicitly registered
    if "simplex_mind" not in projects:
        result.append(dict(_SIMPLEX_MIND_ENTRY))
    return result


def _get_current_branch() -> Optional[str]:
    """Return the current simplex_mind git branch name, or None if unavailable.
    Cached per process — the branch cannot change mid-invocation."""
    global _branch_cache
    if _branch_cache is not ...:
        return _branch_cache

    branch = None
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=str(_REPO_ROOT),
            timeout=5,
        )
        if result.returncode == 0:
            branch = result.stdout.strip() or None
    except Exception:
        pass
    _branch_cache = branch
    return branch


def get_active_project() -> Optional[Dict[str, Any]]:
    """Return the project whose branch matches the current simplex_mind git
    branch, or None. On master (or any unmapped branch), returns None."""
    current = _get_current_branch()
    if not current:
        return None
    for cfg in load_projects().values():
        if cfg.get("branch") == current:
            return cfg
    return None


def get_project(name: str) -> Optional[Dict[str, Any]]:
    """Look up a project by name. Returns None if not found."""
    projects = load_projects()
    if name in projects:
        return projects[name]
    if name == "simplex_mind":
        # Check if explicitly registered first
        return projects.get("simplex_mind", dict(_SIMPLEX_MIND_ENTRY))
    return None


def get_ticket_db_path(target: Optional[str] = None) -> Path:
    """
    Resolve the ticket database path for a project.

    Args:
        target: Project name. If None, uses active project.

    Returns:
        Path to <project_path>/database/tickets.db
    """
    if target:
        proj = get_project(target)
        if not proj:
            # An explicitly named target must resolve — falling through to the
            # active project would silently misroute tickets into the wrong DB.
            raise ValueError(
                f"Unknown project target '{target}' — not registered in projects.yaml"
            )
        return Path(proj["path"]) / "database" / "tickets.db"

    # Fall back to active project
    active = get_active_project()
    if active:
        return Path(active["path"]) / "database" / "tickets.db"

    # Last resort: simplex_mind brain DB
    return _REPO_ROOT / "database" / "tickets.db"


def get_ticket_prefix(target: Optional[str] = None) -> str:
    """
    Resolve the ticket prefix for a project.

    Args:
        target: Project name. If None, uses active project.

    Returns:
        Prefix string (e.g. "CORN", "SHOP", "SIMP")
    """
    if target:
        proj = get_project(target)
        if not proj:
            raise ValueError(
                f"Unknown project target '{target}' — not registered in projects.yaml"
            )
        return proj["ticket_prefix"]

    active = get_active_project()
    if active:
        return active["ticket_prefix"]

    return "SIMP"


def infer_project_from_prefix(ticket_id: str) -> Optional[str]:
    """
    Given a ticket ID like 'SHOP-122', extract the prefix and find the
    matching project in projects.yaml.

    Returns:
        Project name or None if no match found.
    """
    if "-" not in ticket_id:
        return None
    prefix = ticket_id.split("-", 1)[0].upper()

    for proj in get_all_projects():
        if proj["ticket_prefix"].upper() == prefix:
            return proj["name"]

    return None
