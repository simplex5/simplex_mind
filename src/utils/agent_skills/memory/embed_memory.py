"""
Tool: Memory Embedding Generator
Purpose: Generate vector embeddings for memory entries to enable semantic search

Backend preference (fully local first):
1. fastembed (local ONNX model, no API key, no network after first model download)
2. OpenAI text-embedding-3-small (requires openai package + OPENAI_API_KEY)

Stores embeddings as BLOBs in SQLite for manual cosine similarity search.

Usage:
    python src/utils/agent_skills/memory/embed_memory.py --all              # Embed all entries without embeddings
    python src/utils/agent_skills/memory/embed_memory.py --id 5             # Embed a specific entry
    python src/utils/agent_skills/memory/embed_memory.py --content "text"   # Get embedding for arbitrary text
    python src/utils/agent_skills/memory/embed_memory.py --stats            # Show embedding statistics
    python src/utils/agent_skills/memory/embed_memory.py --reindex          # Re-embed all entries

Dependencies:
    - fastembed (preferred, local) OR openai (fallback, remote)
    - sqlite3 (stdlib)

Env Vars:
    - OPENAI_API_KEY (only for the OpenAI fallback)
    - HELICONE_API_KEY (optional, for observability with OpenAI)

Output:
    JSON result with success status and embedding info
"""

import os
import sys
import json
import argparse
import struct
from pathlib import Path
from typing import List, Dict, Any

try:
    from .._common import REPO_ROOT as _REPO_ROOT
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from _common import REPO_ROOT as _REPO_ROOT

# Embedding backends are installed in the repo venv, but callers invoke these
# tools with system python3 (Stop hook) as well as venv/bin/python (cron).
# Expose the venv's site-packages to system python so both paths work.
_VENV_SITE_CANDIDATES = (
    _REPO_ROOT / "venv" / "lib"
    / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages",
    _REPO_ROOT / "venv" / "Lib" / "site-packages",  # Windows venv layout
)
if sys.prefix == sys.base_prefix:
    for _venv_site in _VENV_SITE_CANDIDATES:
        if _venv_site.is_dir() and str(_venv_site) not in sys.path:
            sys.path.insert(0, str(_venv_site))
            break

# Optional .env loading — never a hard dependency
try:
    from .._common import load_dotenv_if_available
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from _common import load_dotenv_if_available
load_dotenv_if_available()

# Local embedding backend (preferred)
try:
    from fastembed import TextEmbedding
    HAS_FASTEMBED = True
except ImportError:
    HAS_FASTEMBED = False

# OpenAI backend (fallback)
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# Import memory_db functions
try:
    from .memory_db import (
        get_entries_without_embeddings,
        store_embedding,
        get_connection
    )
except ImportError:
    from memory_db import (
        get_entries_without_embeddings,
        store_embedding,
        get_connection
    )

# Constants
LOCAL_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"   # 384-dim, ~130MB, fully local
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"  # 1536-dim, remote

# Persistent model cache — fastembed's default lands under /tmp, which is wiped
# on reboot and forces a ~130MB re-download that stalls the first recall-hook
# call after boot (SIMP-L1-027).
FASTEMBED_CACHE_DIR = Path.home() / ".cache" / "simplex_mind" / "fastembed"

# Lazy-initialized local model (first call downloads the ONNX model to cache)
_local_model = None


def _get_local_model():
    global _local_model
    if _local_model is None:
        FASTEMBED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _local_model = TextEmbedding(
            model_name=LOCAL_EMBEDDING_MODEL,
            cache_dir=str(FASTEMBED_CACHE_DIR),
        )
    return _local_model


def get_openai_client():
    """Get OpenAI client with optional Helicone proxy."""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    # Check for Helicone
    helicone_key = os.getenv('HELICONE_API_KEY')
    if helicone_key:
        return OpenAI(
            api_key=api_key,
            base_url="https://oai.helicone.ai/v1",
            default_headers={
                "Helicone-Auth": f"Bearer {helicone_key}",
                "Helicone-Property-Tool": "embed_memory"
            }
        )
    else:
        return OpenAI(api_key=api_key)


def embedding_to_bytes(embedding: List[float]) -> bytes:
    """Convert embedding list to bytes for storage."""
    return struct.pack(f'{len(embedding)}f', *embedding)


def bytes_to_embedding(data: bytes) -> List[float]:
    """Convert bytes back to embedding list."""
    count = len(data) // 4  # 4 bytes per float
    return list(struct.unpack(f'{count}f', data))


def generate_embedding(text: str, client=None) -> Dict[str, Any]:
    """
    Generate embedding for a text string.

    Prefers the local fastembed backend; falls back to OpenAI when fastembed
    is unavailable but openai + OPENAI_API_KEY are present.

    Args:
        text: Text to embed
        client: Optional OpenAI client (only used on the OpenAI path)

    Returns:
        dict with embedding and metadata (model records which backend produced it)
    """
    if HAS_FASTEMBED:
        try:
            vector = next(iter(_get_local_model().embed([text])))
            embedding = [float(x) for x in vector]
            return {
                "success": True,
                "embedding": embedding,
                "model": LOCAL_EMBEDDING_MODEL,
                "dimensions": len(embedding),
                "usage": {"prompt_tokens": 0, "total_tokens": 0}
            }
        except Exception as e:
            return {"success": False, "error": f"fastembed failed: {e}"}

    if HAS_OPENAI and os.getenv('OPENAI_API_KEY'):
        if client is None:
            client = get_openai_client()
        try:
            response = client.embeddings.create(
                model=OPENAI_EMBEDDING_MODEL,
                input=text,
                encoding_format="float"
            )
            embedding = response.data[0].embedding
            return {
                "success": True,
                "embedding": embedding,
                "model": OPENAI_EMBEDDING_MODEL,
                "dimensions": len(embedding),
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    return {
        "success": False,
        "error": "No embedding backend available — install fastembed (local, preferred) "
                 "or openai + set OPENAI_API_KEY"
    }


def embed_entry(entry_id: int, client=None) -> Dict[str, Any]:
    """
    Generate and store embedding for a memory entry.

    Args:
        entry_id: Memory entry ID
        client: Optional OpenAI client

    Returns:
        dict with success status
    """
    # Fetch content directly — get_entry() would bump access_count and write
    # an access-log row, polluting usage analytics with embedding runs.
    conn = get_connection()
    row = conn.execute(
        'SELECT content FROM memory_entries WHERE id = ?', (entry_id,)
    ).fetchone()
    conn.close()

    if row is None:
        return {"success": False, "error": f"Memory entry {entry_id} not found"}

    content = row['content'] or ''
    if not content:
        return {"success": False, "error": f"Entry {entry_id} has no content"}

    # Generate embedding
    embed_result = generate_embedding(content, client)
    if not embed_result.get('success'):
        return embed_result

    # Store embedding, recording which backend model produced it
    embedding_bytes = embedding_to_bytes(embed_result['embedding'])
    store_result = store_embedding(entry_id, embedding_bytes, embed_result['model'])

    return {
        "success": store_result.get('success', False),
        "entry_id": entry_id,
        "content_preview": content[:100] + "..." if len(content) > 100 else content,
        "dimensions": embed_result['dimensions'],
        "tokens_used": embed_result['usage']['total_tokens'],
        "model": embed_result['model']
    }


def embed_all_pending(batch_size: int = 50, client=None) -> Dict[str, Any]:
    """
    Embed all entries that don't have embeddings yet.

    Args:
        batch_size: Number of entries to process
        client: Optional OpenAI client

    Returns:
        dict with batch results
    """
    # Client is only needed on the OpenAI path; generate_embedding creates one
    # lazily there. Requiring it up front would break the local backend.

    # Get entries without embeddings
    pending = get_entries_without_embeddings(limit=batch_size)
    if not pending.get('success'):
        return pending

    entries = pending.get('entries', [])
    if not entries:
        return {"success": True, "message": "No entries need embedding", "processed": 0}

    results = {
        "success": True,
        "processed": 0,
        "failed": 0,
        "total_tokens": 0,
        "entries": []
    }

    # Fast path (SIMP-L1-035): one batched model call + one DB connection for
    # the whole batch, instead of a model call + 2 connections per entry.
    batched = False
    if HAS_FASTEMBED:
        try:
            model = _get_local_model()
            vectors = list(model.embed([e['content'] for e in entries]))
            conn = get_connection()
            cursor = conn.cursor()
            for entry, vec in zip(entries, vectors):
                emb_bytes = embedding_to_bytes([float(x) for x in vec])
                cursor.execute('''
                    UPDATE memory_entries
                    SET embedding = ?, embedding_model = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (emb_bytes, LOCAL_EMBEDDING_MODEL, entry['id']))
                results['processed'] += 1
                results['entries'].append({"id": entry['id'], "success": True, "error": None})
            conn.commit()
            conn.close()
            batched = True
        except Exception as e:
            # Fall back to the per-entry path below
            results = {"success": True, "processed": 0, "failed": 0,
                       "total_tokens": 0, "entries": [],
                       "batch_fallback": f"batched embed failed: {e}"}

    if not batched:
        for entry in entries:
            entry_id = entry['id']
            result = embed_entry(entry_id, client)

            if result.get('success'):
                results['processed'] += 1
                results['total_tokens'] += result.get('tokens_used', 0)
            else:
                results['failed'] += 1

            results['entries'].append({
                "id": entry_id,
                "success": result.get('success', False),
                "error": result.get('error')
            })

    # Calculate cost (~$0.02 per 1M tokens)
    results['estimated_cost'] = f"${results['total_tokens'] * 0.00002:.6f}"

    return results


def reindex_all(batch_size: int = 100, client=None) -> Dict[str, Any]:
    """
    Re-embed all entries (regenerate all embeddings).

    Loops in batches until nothing is left pending — a single batch would
    leave every entry beyond batch_size permanently without an embedding.

    Args:
        batch_size: Number of entries to process per batch
        client: Optional OpenAI client (OpenAI path only)

    Returns:
        dict with aggregated reindex results
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Clear existing embeddings
    cursor.execute('UPDATE memory_entries SET embedding = NULL, embedding_model = NULL')
    conn.commit()
    conn.close()

    totals = {"success": True, "processed": 0, "failed": 0, "total_tokens": 0, "batches": 0}
    while True:
        result = embed_all_pending(batch_size=batch_size, client=client)
        if not result.get('success'):
            return result
        processed = result.get('processed', 0)
        failed = result.get('failed', 0)
        if processed == 0 and failed == 0:
            break  # nothing pending
        totals["batches"] += 1
        totals["processed"] += processed
        totals["failed"] += failed
        totals["total_tokens"] += result.get('total_tokens', 0)
        if processed == 0:
            # Every remaining entry failed — stop instead of looping forever
            totals["success"] = False
            totals["error"] = "All entries in last batch failed to embed"
            break

    totals['estimated_cost'] = f"${totals['total_tokens'] * 0.00002:.6f}"
    return totals


def get_embedding_stats() -> Dict[str, Any]:
    """Get statistics about embeddings in the database."""
    conn = get_connection()
    cursor = conn.cursor()

    # Total entries
    cursor.execute('SELECT COUNT(*) as total FROM memory_entries WHERE is_active = 1')
    total = cursor.fetchone()['total']

    # With embeddings
    cursor.execute('SELECT COUNT(*) as count FROM memory_entries WHERE embedding IS NOT NULL AND is_active = 1')
    with_embeddings = cursor.fetchone()['count']

    # Without embeddings
    cursor.execute('SELECT COUNT(*) as count FROM memory_entries WHERE embedding IS NULL AND is_active = 1')
    without_embeddings = cursor.fetchone()['count']

    # By model
    cursor.execute('''
        SELECT embedding_model, COUNT(*) as count
        FROM memory_entries
        WHERE embedding IS NOT NULL AND is_active = 1
        GROUP BY embedding_model
    ''')
    by_model = {row['embedding_model']: row['count'] for row in cursor.fetchall()}

    # Average content length for entries with embeddings
    cursor.execute('''
        SELECT AVG(LENGTH(content)) as avg_length
        FROM memory_entries
        WHERE embedding IS NOT NULL AND is_active = 1
    ''')
    avg_length = cursor.fetchone()['avg_length'] or 0

    conn.close()

    return {
        "success": True,
        "stats": {
            "total_active_entries": total,
            "with_embeddings": with_embeddings,
            "without_embeddings": without_embeddings,
            "coverage_percent": round(with_embeddings / total * 100, 1) if total > 0 else 0,
            "by_model": by_model,
            "avg_content_length": round(avg_length, 0)
        }
    }


def main():
    parser = argparse.ArgumentParser(description='Memory Embedding Generator')
    parser.add_argument('--all', action='store_true', help='Embed all entries without embeddings')
    parser.add_argument('--id', type=int, help='Embed a specific entry by ID')
    parser.add_argument('--content', help='Get embedding for arbitrary text (returns JSON)')
    parser.add_argument('--reindex', action='store_true', help='Re-embed all entries')
    parser.add_argument('--stats', action='store_true', help='Show embedding statistics')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size for --all')

    args = parser.parse_args()

    result = None

    if args.stats:
        result = get_embedding_stats()

    elif args.content:
        # Just get embedding for text (backend availability handled inside)
        result = generate_embedding(args.content)
        # Don't print full embedding, just metadata
        if result.get('success'):
            result['embedding_preview'] = result['embedding'][:5] + ['...']
            del result['embedding']

    elif args.id:
        result = embed_entry(args.id)

    elif args.reindex:
        print("Re-indexing all entries (this will clear existing embeddings)...")
        result = reindex_all(batch_size=args.batch_size)

    elif args.all:
        result = embed_all_pending(batch_size=args.batch_size)

    else:
        parser.print_help()
        sys.exit(0)

    if result:
        if result.get('success'):
            print(f"OK {result.get('message', 'Success')}")
        else:
            print(f"ERROR {result.get('error', 'Unknown error')}")
            sys.exit(1)

        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
