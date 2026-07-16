#!/usr/bin/env python3
"""
Tool: Subconscious Indexer
Purpose: Build the retrieval index for the subconscious — the context-triggered
         reasoning-philosophy layer. Reads philosophy pieces from the repo's own
         subconscious/ directory, merges in this machine's personal trigger
         keywords, embeds each piece, and writes
         database/memory/subconscious_index.json.

Trigger keywords are TWO LAYERS, merged at build time:
- Piece frontmatter `keywords:` (committed) — generic defaults anyone would
  say, so the feature works out of the box on a fresh machine.
- Local overlay (gitignored, like projects.yaml) — personal phrasing that
  encodes how one specific user talks; never committed:

    database/memory/subconscious_keywords.json
    {"<piece-name>": ["phrase", ...], ...}

Tune keywords for a new machine/user by running subconscious_mine.py over that
machine's own conversation history and curating into the overlay. A piece with
no keywords still works — it matches on embedding similarity only.

The index is self-contained (embeds full piece text + merged keywords). Re-run
after adding or editing pieces or the keyword overlay.

Piece format (subconscious/*.md):
    ---
    name: <slug>
    summary: <one line>
    keywords:
      - <generic phrase>
    source: <provenance note>
    ---
    <prose body>

Usage:
    python3 subconscious_index.py          # build/rebuild
    python3 subconscious_index.py --list   # show indexed pieces
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
LIB_PATH = _REPO_ROOT / "subconscious"
INDEX_PATH = _REPO_ROOT / "database" / "memory" / "subconscious_index.json"
KEYWORDS_PATH = _REPO_ROOT / "database" / "memory" / "subconscious_keywords.json"


def parse_piece(path: Path) -> dict:
    """Parse frontmatter + body. Minimal parser — the frontmatter grammar is
    flat keys plus one list, same tolerance as project_resolver's YAML fallback."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        raise ValueError(f"{path.name}: missing frontmatter")
    front, body = m.group(1), m.group(2).strip()
    meta = {"keywords": []}
    current_list = None
    for line in front.split("\n"):
        if re.match(r"^\s+-\s+", line) and current_list is not None:
            current_list.append(line.split("-", 1)[1].strip())
        elif ":" in line:
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()
            if value:
                meta[key] = value
                current_list = None
            else:
                meta[key] = []
                current_list = meta[key]
    if not meta.get("name"):
        raise ValueError(f"{path.name}: frontmatter needs at least a name")
    meta["body"] = body
    meta["file"] = path.name
    return meta


def load_keyword_overlay() -> dict:
    """Load the local (gitignored) per-piece keyword overlay. Missing file is
    fine — pieces then match semantic-only until keywords are curated."""
    if not KEYWORDS_PATH.exists():
        return {}
    overlay = json.loads(KEYWORDS_PATH.read_text(encoding="utf-8"))
    if not isinstance(overlay, dict):
        raise ValueError(f"{KEYWORDS_PATH}: expected a JSON object of name -> [phrases]")
    return {name: [str(k) for k in kws] for name, kws in overlay.items()}


def merged_keywords(piece: dict, overlay: dict) -> list:
    """Frontmatter keywords (if any) + local overlay, deduped, order preserved."""
    seen = set()
    merged = []
    for kw in piece["keywords"] + overlay.get(piece["name"], []):
        key = kw.lower().strip()
        if key and key not in seen:
            seen.add(key)
            merged.append(kw)
    return merged


def build_index() -> int:
    lib = LIB_PATH
    if not lib.is_dir():
        print(f"Library directory not found: {lib}")
        return 1

    pieces = [parse_piece(p) for p in sorted(lib.glob("*.md")) if p.name != "README.md"]
    if not pieces:
        print(f"No pieces in {lib}")
        return 1

    overlay = load_keyword_overlay()
    for p in pieces:
        p["keywords"] = merged_keywords(p, overlay)
        if not p["keywords"]:
            print(f"WARNING: {p['name']} has no keywords (semantic-only matching) — "
                  f"curate some into {KEYWORDS_PATH.name} via subconscious_mine.py")
    unknown = sorted(set(overlay) - {p["name"] for p in pieces})
    if unknown:
        print(f"WARNING: keyword overlay names no existing piece: {', '.join(unknown)}")

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "memory"))
    import embed_memory
    model = embed_memory._get_local_model()
    texts = [f"{p.get('summary', '')}\n{p['body']}" for p in pieces]
    embeddings = [e.tolist() for e in model.embed(texts)]

    index = {
        "model": embed_memory.LOCAL_EMBEDDING_MODEL,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "library": str(lib),
        "pieces": [
            {
                "name": p["name"],
                "file": p["file"],
                "summary": p.get("summary", ""),
                "keywords": p["keywords"],
                "source": p.get("source", ""),
                "text": p["body"],
                "embedding": emb,
            }
            for p, emb in zip(pieces, embeddings)
        ],
    }
    INDEX_PATH.write_text(json.dumps(index), encoding="utf-8")
    print(f"Indexed {len(pieces)} pieces from {lib}")
    print(f"-> {INDEX_PATH} ({INDEX_PATH.stat().st_size // 1024} KB)")
    return 0


def list_index() -> int:
    if not INDEX_PATH.exists():
        print("No index built yet.")
        return 1
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    print(f"model={index['model']}  built={index['built_at']}  library={index['library']}")
    for p in index["pieces"]:
        print(f"  {p['name']:28s} kw={len(p['keywords'])} chars={len(p['text'])}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the subconscious retrieval index")
    parser.add_argument("--list", action="store_true", help="Show indexed pieces")
    args = parser.parse_args()
    sys.exit(list_index() if args.list else build_index())
