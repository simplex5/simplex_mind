"""
Tool: Project Resolver
Purpose: Shared utility for resolving project config from projects.yaml.
         Used by ticket system, memory tools, and session digest to route
         operations to the correct per-project database.

Functions:
    load_projects()              -> dict of project configs
    get_active_project()         -> {name, path, prefix, ref_file} for active project
    get_project(name)            -> config for a specific project
    get_ticket_db_path(target)   -> Path to <project_path>/database/tickets.db
    get_all_projects()           -> list of all project configs
    infer_project_from_prefix(ticket_id) -> project name matching the prefix

Resolution order for ticket DB:
    1. Explicit target (project name)
    2. Prefix inference from ticket ID
    3. Active project (default)
    4. Fallback: simplex_mind brain DB (prefix SIMP)
"""

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
    "active": False,
}


def _parse_yaml(text: str) -> dict:
    """Parse projects.yaml. Uses PyYAML if available, otherwise minimal parser."""
    if yaml:
        return yaml.safe_load(text) or {}

    # Minimal fallback parser for the simple projects.yaml structure
    projects = {}
    current_project = None
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith("    ") and ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip("'\"")
            if current_project and key in ("path", "ref_file", "ticket_prefix", "active"):
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
                projects[current_project][key] = value
        elif line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            current_project = stripped[:-1].strip()
            projects[current_project] = {}

    return {"projects": projects}


def load_projects() -> Dict[str, Dict[str, Any]]:
    """Parse projects.yaml and return dict of {name: config}."""
    if not _PROJECTS_YAML.exists():
        return {}
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
            "active": cfg.get("active", False),
        }
    return result


def get_all_projects() -> List[Dict[str, Any]]:
    """Return all registered projects including implicit simplex_mind entry."""
    projects = load_projects()
    result = list(projects.values())
    # Add simplex_mind if not explicitly registered
    if "simplex_mind" not in projects:
        result.append(dict(_SIMPLEX_MIND_ENTRY))
    return result


def get_active_project() -> Optional[Dict[str, Any]]:
    """Return the project with active: true, or None."""
    for cfg in load_projects().values():
        if cfg.get("active"):
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
        if proj:
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
        if proj:
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
