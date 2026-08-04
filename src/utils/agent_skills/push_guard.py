"""
Tool: Push Guard (PreToolUse hook — SIMP-D2-053)
Purpose: Deterministic enforcement of the branch-publication rule: only
         `master` and `develop` are EVER pushed for the simplex_mind repo.
         On 2026-08-04 the orchestrator pushed the `animal-town` project
         branch to origin by momentum — the prose rule (condition-shaped)
         did not fire at push time, the exact SIMP-D2-017 failure mode.
         Instructions carry routing; hooks carry enforcement.

Fires on Bash/PowerShell tool calls (settings.json matcher). When a segment of
the command is a `git push` whose effective directory is inside the simplex_mind
repo, the decision matrix in plans/2026-08-04_push-guard-hook.md applies.

DESIGN DEPARTURES from the hook family (deliberate, reviewed):
- This is the family's FIRST DENYING HOOK. Every sibling documents "never emits
  a permissionDecision"; this one denies, because publishing a branch is
  outward-facing and effectively irreversible once fetched, and a warn was
  already tried by proxy (the CLAUDE.md rule) and failed.
- ZERO ask rows. Once a brain-repo push is established, every remaining
  ambiguity (unresolvable branch, unknown flag shape) DENIES — approval-under-
  momentum is the failure mode that caused the incident, so an "ask" dialog is
  not fail-safe. Every deny message names the remediation: run the push by hand
  in a terminal — the hook only governs agent-driven tool calls.
- Fail-open OUTER: a crashed guard prints a degraded marker and exits 0 with no
  decision. Fail-toward-deny INNER: uncertainty after a brain-push is
  established never falls through to allow.

Accepted limitations (mistakes-not-adversaries — the actor guarded is the
agent, not an attacker):
- Tags pushed BY NAME (`git push origin v1.2.0`) are denied — the parser cannot
  cheaply distinguish a tag from a branch. Remediation: `--tags` (allowed) or a
  hand-run push. This false positive is accepted, do not "fix" it into a hole.
- Command substitution / variable indirection can evade the parser.
- A simplex_mind WORKTREE at another path evades the path-prefix repo check.
- Remote allowlist is by NAME (`origin` or absent): a `git remote rename`
  evasion is adversarial-tier and out of scope.

Markers: `[push-guard: denied '<subject>' — ...]` on deny,
         `[push-guard: allowed delete of '<ref>' — remediation path]`,
         `[push-guard degraded: <reason> — run doctor.py]` when the guard
         itself breaks (no decision emitted — harness default flow applies).
"""

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from ._common import REPO_ROOT as _REPO_ROOT
    from .memory import hook_state
except ImportError:
    from _common import REPO_ROOT as _REPO_ROOT
    from memory import hook_state

GATED_TOOLS = {"Bash", "PowerShell"}
ALLOWED_BRANCHES = {"master", "develop"}
PROTECTED_DELETE = {"master", "develop", "main"}
ALLOWED_REMOTES = {None, "origin"}

# Tokens that legitimately precede a command head — `git` after one of these is
# in command position; `git` after anything else (e.g. `echo git push`) is data.
_CMD_PREFIX = {"{", "(", "if", "then", "else", "do", "sudo", "env", "!", "time"}

# push flags that take NO argument (safe to skip without shifting positionals)
_NOARG_FLAGS = {
    "--delete", "-d", "--force", "-f", "--force-with-lease", "--all", "--mirror",
    "--tags", "--dry-run", "-n", "-u", "--set-upstream", "-q", "--quiet",
    "-v", "--verbose", "--porcelain", "--progress", "--no-verify", "--verify",
    "--follow-tags", "--atomic", "--prune", "--no-force-with-lease",
}
# push flags that CONSUME the next token as their value
_ARG_FLAGS = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}

DENY_POLICY = (
    "Only master/develop are ever pushed for the simplex_mind repo. If this push is "
    "intended, run it yourself in a terminal (`! git push ...`) — the hook only "
    "governs agent-driven tool calls."
)


def _tokenize(segment: str) -> list:
    """Whitespace split respecting single/double quotes (quotes stripped)."""
    tokens, cur, quote = [], [], None
    for ch in segment:
        if quote:
            if ch == quote:
                quote = None
            else:
                cur.append(ch)
        elif ch in "'\"":
            quote = ch
        elif ch.isspace():
            if cur:
                tokens.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        tokens.append("".join(cur))
    return tokens


def split_segments(command: str) -> list:
    """Split a shell command into segments on &&, ||, ;, |, and newlines —
    outside quotes only."""
    segments, cur, quote = [], [], None
    i, n = 0, len(command)
    while i < n:
        ch = command[i]
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            cur.append(ch)
            i += 1
            continue
        if command.startswith("&&", i) or command.startswith("||", i):
            segments.append("".join(cur))
            cur = []
            i += 2
            continue
        if ch in ";|\n":
            segments.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    segments.append("".join(cur))
    return [s.strip() for s in segments if s.strip()]


def effective_dirs(segments: list, cwd: str) -> list:
    """Pair each segment with the directory in effect WHEN IT RUNS, tracking
    cd / Set-Location / Push-Location (a cd's own segment keeps the prior dir)."""
    pairs, current = [], cwd
    for seg in segments:
        pairs.append((seg, current))
        tokens = _tokenize(seg)
        if tokens and tokens[0].lower() in ("cd", "set-location", "push-location", "sl", "pushd"):
            if len(tokens) > 1 and not tokens[1].startswith("-"):
                target = tokens[1]
                current = target if os.path.isabs(target) else os.path.normpath(
                    os.path.join(current, target))
    return pairs


@dataclass
class PushCommand:
    c_path: str = None
    remote: str = None
    refspecs: list = field(default_factory=list)
    delete: bool = False
    force: bool = False
    all_flag: bool = False
    mirror: bool = False
    tags: bool = False
    ambiguous: bool = False


def parse_push(segment: str):
    """Return a PushCommand if this segment runs `git ... push ...`, else None.
    `git` must be in command position (segment head or after {, (, if, …) so
    `echo git push` stays data, while `if ($?) { git push … }` is caught."""
    tokens = _tokenize(segment)
    git_idx = None
    for i, tok in enumerate(tokens):
        if tok == "git" and (i == 0 or tokens[i - 1] in _CMD_PREFIX):
            git_idx = i
            break
    if git_idx is None:
        return None

    parsed = PushCommand()
    i = git_idx + 1
    # git global flags before the subcommand
    while i < len(tokens):
        tok = tokens[i]
        if tok == "-C":
            parsed.c_path = tokens[i + 1] if i + 1 < len(tokens) else None
            i += 2
        elif tok == "-c":
            i += 2
        elif tok.startswith("--git-dir") or tok.startswith("--work-tree"):
            i += 1 if "=" in tok else 2
        elif tok in ("-p", "--paginate", "--no-pager"):
            i += 1
        else:
            break
    if i >= len(tokens) or tokens[i] != "push":
        return None
    i += 1

    while i < len(tokens):
        tok = tokens[i]
        if tok in ("}", ")"):
            break
        if tok in _ARG_FLAGS:
            i += 2
            continue
        if tok.startswith("--push-option=") or tok.startswith("--repo=") or \
                tok.startswith("--receive-pack=") or tok.startswith("--exec=") or \
                tok.startswith("--force-with-lease="):
            i += 1
            continue
        if tok in _NOARG_FLAGS:
            if tok in ("--delete", "-d"):
                parsed.delete = True
            elif tok in ("--force", "-f", "--force-with-lease"):
                parsed.force = True
            elif tok == "--all":
                parsed.all_flag = True
            elif tok == "--mirror":
                parsed.mirror = True
            elif tok == "--tags":
                parsed.tags = True
            i += 1
            continue
        if tok.startswith("-"):
            parsed.ambiguous = True  # unknown flag: cannot tell if it eats the next token
            i += 1
            continue
        if parsed.remote is None:
            parsed.remote = tok
        else:
            parsed.refspecs.append(tok)
        i += 1
    return parsed


def _norm(ref: str) -> str:
    return ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref


def _current_branch(git_dir):
    """`git branch --show-current` in the target dir; None on any failure."""
    try:
        out = subprocess.run(["git", "-C", str(git_dir), "branch", "--show-current"],
                             capture_output=True, text=True, timeout=5)
        branch = out.stdout.strip()
        return branch if out.returncode == 0 and branch else None
    except Exception:
        return None


def decide(parsed: PushCommand, effective_dir: str, repo_root, branch_fn):
    """Apply the decision matrix. Returns (kind, reason, subject) where kind is
    'allow' | 'deny' | 'allow-delete' | 'skip'."""
    target = Path(parsed.c_path) if parsed.c_path and os.path.isabs(parsed.c_path) \
        else Path(effective_dir) / (parsed.c_path or "")
    try:
        inside = target.resolve().is_relative_to(Path(repo_root).resolve())
    except Exception:
        inside = True  # resolution trouble on a possible brain push: stay suspicious
    if not inside:
        return ("skip", "outside-brain", "")

    if parsed.ambiguous:  # first: an ambiguous parse makes every other field untrustworthy
        return ("deny", "parse-ambiguity", "unrecognized flag shape")
    if parsed.remote not in ALLOWED_REMOTES:
        return ("deny", "remote-not-origin", parsed.remote)
    if parsed.mirror or parsed.all_flag:
        return ("deny", "publishes-all-branches", "--mirror" if parsed.mirror else "--all")

    def resolve_ref(ref):
        ref = _norm(ref)
        if ref in ("HEAD", "@"):
            return branch_fn(target)
        return ref

    if parsed.delete:
        for ref in parsed.refspecs:
            if _norm(ref) in PROTECTED_DELETE:
                return ("deny", "delete-protected", _norm(ref))
        return ("allow-delete", "remediation-path",
                ", ".join(_norm(r) for r in parsed.refspecs) or "(unnamed)")

    if parsed.tags and not parsed.refspecs:
        return ("allow", "tags-only", "")

    if not parsed.refspecs:
        branch = branch_fn(target)
        if branch is None:
            return ("deny", "branch-unresolvable", "current branch")
        if branch not in ALLOWED_BRANCHES:
            return ("deny", "ref-not-allowed", branch)
        if parsed.force:
            return ("deny", "force-to-protected", branch)
        return ("allow", "allowed", branch)

    pending_delete = None
    for raw in parsed.refspecs:
        force_this = parsed.force or raw.startswith("+")
        spec = raw.lstrip("+")
        if ":" in spec:
            src, dst = spec.split(":", 1)
            if src == "":  # `:ref` colon-delete
                d = _norm(dst)
                if d in PROTECTED_DELETE:
                    return ("deny", "delete-protected", d)
                pending_delete = d
                continue
            if dst == "":
                return ("deny", "parse-ambiguity", raw)
            rdst, rsrc = resolve_ref(dst), resolve_ref(src)
            if rdst is None or rsrc is None:
                return ("deny", "branch-unresolvable", raw)
            if rdst not in ALLOWED_BRANCHES:
                return ("deny", "ref-not-allowed", rdst)
            if rsrc not in ALLOWED_BRANCHES:
                return ("deny", "cross-publish-src", f"{rsrc}:{rdst}")
            if force_this:
                return ("deny", "force-to-protected", rdst)
        else:
            r = resolve_ref(spec)
            if r is None:
                return ("deny", "branch-unresolvable", raw)
            if r not in ALLOWED_BRANCHES:
                return ("deny", "ref-not-allowed", r)
            if force_this:
                return ("deny", "force-to-protected", r)
    if pending_delete is not None:
        return ("allow-delete", "remediation-path", pending_delete)
    return ("allow", "allowed", "")


def main() -> int:
    t0 = time.time()
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    except Exception:
        return 0  # unparseable hook payload — nothing sane to do, fail open
    session_id = re.sub(r"[^A-Za-z0-9_-]", "_", str(data.get("session_id", "unknown")))[:64]

    def _done(outcome: str, reason: str = "") -> int:
        hook_state.log_event("push_guard", session_id, "invocation", outcome,
                             reason=reason, duration_ms=int((time.time() - t0) * 1000))
        return 0

    if data.get("tool_name") not in GATED_TOOLS:
        return _done("skipped", "ungated-tool")
    command = (data.get("tool_input") or {}).get("command") or ""
    if "push" not in command:  # cheap pre-filter; full parse below
        return _done("skipped", "not-a-push")
    cwd = data.get("cwd") or "."

    try:
        deletes, pushes_seen, outside_seen = [], 0, 0
        for segment, eff_dir in effective_dirs(split_segments(command), cwd):
            parsed = parse_push(segment)
            if parsed is None:
                continue
            pushes_seen += 1
            kind, reason, subject = decide(parsed, eff_dir, _REPO_ROOT, _current_branch)
            if kind == "deny":
                print(json.dumps({
                    "systemMessage": f"[push-guard: denied '{subject}' — only master/develop "
                                     f"go online for simplex_mind]",
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": f"Push guard (SIMP-D2-053): {reason} "
                                                    f"('{subject}'). {DENY_POLICY}",
                    },
                }))
                return _done("fired", reason)
            if kind == "allow-delete":
                deletes.append(subject)
            if reason == "outside-brain":
                outside_seen += 1
        if deletes:
            print(json.dumps({"systemMessage":
                              f"[push-guard: allowed delete of '{', '.join(deletes)}' — "
                              f"remediation path]"}))
            return _done("allowed-delete", "remediation-path")
        if pushes_seen and outside_seen == pushes_seen:
            return _done("skipped", "outside-brain")
        return _done("skipped", "allowed" if pushes_seen else "no-push-segment")
    except Exception as e:
        print(json.dumps({"systemMessage":
                          f"[push-guard degraded: {type(e).__name__} — run doctor.py]"}))
        return _done("degraded", type(e).__name__)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail-open, always
