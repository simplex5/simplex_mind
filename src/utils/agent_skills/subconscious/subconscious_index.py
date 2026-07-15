#!/usr/bin/env python3
"""
Tool: Subconscious Indexer
Purpose: Build the retrieval index for the subconscious — the context-triggered
         reasoning-philosophy layer. Reads keyword-tagged philosophy pieces from
         the library project's subconscious/ directory (project named by the
         top-level `subconscious:` key in projects.yaml), embeds each piece, and
         writes database/memory/subconscious_index.json.

The index is self-contained (embeds full piece text), so recall at prompt time
never touches the library project. Re-run after adding or editing pieces.

Piece format (<library>/subconscious/*.md):
    ---
    name: <slug>
    summary: <one line>
    keywords:
      - <phrase>
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from project_resolver import get_subconscious_source  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[4]
INDEX_PATH = _REPO_ROOT / "database" / "memory" / "subconscious_index.json"


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
    if not meta.get("name") or not meta.get("keywords"):
        raise ValueError(f"{path.name}: frontmatter needs at least name + keywords")
    meta["body"] = body
    meta["file"] = path.name
    return meta


def build_index() -> int:
    source = get_subconscious_source()
    if not source:
        print("No `subconscious:` key in projects.yaml — nothing to index.")
        return 1
    lib = Path(source["path"]) / "subconscious"
    if not lib.is_dir():
        print(f"Library directory not found: {lib}")
        return 1

    pieces = [parse_piece(p) for p in sorted(lib.glob("*.md"))]
    if not pieces:
        print(f"No pieces in {lib}")
        return 1

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
