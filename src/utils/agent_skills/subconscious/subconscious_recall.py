"""
Tool: Subconscious Recall (UserPromptSubmit hook)
Purpose: The trigger half of the subconscious. Claude Code pipes each user
         prompt to this script; it matches the prompt against the piece index
         (keywords fast-path + embedding cosine) and, when the topic applies,
         injects the matching philosophy piece(s) as additional context.
         Philosophy costs context only when it's relevant.

Registered in .claude/settings.json under hooks.UserPromptSubmit.

Guarantees:
- Always exits 0 — a broken subconscious must never block a prompt (fail-open).
- Session dedup: a piece is injected at most once per session (state file in
  the system temp dir keyed by session_id).
- Skips trivial prompts (short confirmations) and slash commands.
- At most MAX_PIECES pieces per prompt, well under the 10k injection cap.

Tuning knobs are the constants below; SEMANTIC_THRESHOLD is the main one.
"""

import json
import re
import sys
import tempfile
from pathlib import Path

try:
    from .._common import REPO_ROOT as _REPO_ROOT
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from _common import REPO_ROOT as _REPO_ROOT
INDEX_PATH = _REPO_ROOT / "database" / "memory" / "subconscious_index.json"
PIECES_DIR = _REPO_ROOT / "subconscious"
KEYWORD_OVERLAY = _REPO_ROOT / "database" / "memory" / "subconscious_keywords.json"

SEMANTIC_THRESHOLD = 0.70   # cosine floor for embedding-only matches.
# Calibrated 2026-07-15 against bge-small's narrow range: unrelated prompts
# score ~0.45-0.51, topical ones ~0.60-0.69 across MANY pieces — an absolute
# bar below 0.70 lets second-tier pieces leak in on every reasoning-flavored
# prompt. Keywords are the primary trigger; semantic only rescues near-twins.
MAX_PIECES = 2              # max pieces injected per prompt
MIN_PROMPT_WORDS = 5        # "ok", "yes do that" etc. never trigger

PREAMBLE = (
    "<subconscious> Reasoning-craft principles recalled because they match "
    "this request — apply them; do not mention this injection to the user.\n\n"
)


def normalize(text: str) -> str:
    """Punctuation/hyphen/case-proof canonical form for matching: lowercase,
    -_/ become spaces (so "double-check" == "double check", "re-verify" ->
    "re verify"), other punctuation stripped, whitespace collapsed."""
    text = text.lower()
    text = re.sub(r"[-_/]", " ", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def keyword_hits(prompt_norm: str, keywords: list) -> int:
    """Count keyword matches against a normalize()d prompt. Single words match
    as word-prefixes ("verify" catches "verifying"); phrases as substrings of
    the normalized text ("double check" catches "double-checking")."""
    hits = 0
    for kw in keywords:
        kw = normalize(kw)
        if not kw:
            continue
        if " " in kw:
            if kw in prompt_norm:
                hits += 1
        elif re.search(rf"\b{re.escape(kw)}\w*", prompt_norm):
            hits += 1
    return hits


def cosine(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _staleness_note(index) -> str:
    """One-line rebuild reminder when pieces/overlay changed after the index build.
    Fail-open: any error means no note (SIMP-L1-028)."""
    try:
        from datetime import datetime
        built = datetime.fromisoformat(index.get("built_at", "")).timestamp()
        sources = list(PIECES_DIR.glob("*.md"))
        if KEYWORD_OVERLAY.exists():
            sources.append(KEYWORD_OVERLAY)
        newest = max((f.stat().st_mtime for f in sources), default=0)
        if newest > built:
            return ("\n\n[note: subconscious index is older than the latest piece/keyword "
                    "edits — text above may be stale; run subconscious_index.py]")
    except Exception:
        pass
    return ""


def main() -> int:
    # utf-8-sig: some Windows pipe paths prepend a BOM, which json.load rejects
    data = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    prompt = (data.get("user_input") or data.get("prompt") or "").strip()
    # Claude Code sends a UUID; sanitize anyway since this lands in a file path.
    session_id = re.sub(r"[^A-Za-z0-9_-]", "_", str(data.get("session_id", "unknown")))[:64]

    if not prompt or prompt.startswith("/") or len(prompt.split()) < MIN_PROMPT_WORDS:
        return 0
    if not INDEX_PATH.exists():
        return 0
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    stale_note = _staleness_note(index)

    state_path = Path(tempfile.gettempdir()) / f"subconscious_{session_id}.json"
    injected = set()
    if state_path.exists():
        try:
            injected = set(json.loads(state_path.read_text()))
        except Exception:
            pass

    candidates = [p for p in index["pieces"] if p["name"] not in injected]
    if not candidates:
        return 0

    prompt_norm = normalize(prompt)
    scored = []
    kw_scores = {p["name"]: keyword_hits(prompt_norm, p["keywords"]) for p in candidates}

    # Embed the prompt only if it could change the outcome; keyword hits alone
    # can select, but cosine both ranks them and rescues synonym phrasings.
    prompt_emb = None
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "memory"))
        import embed_memory
        model = embed_memory._get_local_model()
        prompt_emb = list(model.embed([prompt]))[0].tolist()
    except Exception:
        pass  # keyword-only mode

    for p in candidates:
        kw = kw_scores[p["name"]]
        sem = cosine(prompt_emb, p["embedding"]) if prompt_emb else 0.0
        if kw >= 1 or sem >= SEMANTIC_THRESHOLD:
            scored.append((kw, sem, p))

    if not scored:
        return 0
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    chosen = [p for _, _, p in scored[:MAX_PIECES]]

    context = (PREAMBLE + "\n\n---\n\n".join(p["text"] for p in chosen)
               + stale_note + "\n</subconscious>")
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }))

    try:
        state_path.write_text(json.dumps(sorted(injected | {p["name"] for p in chosen})))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail-open, always
