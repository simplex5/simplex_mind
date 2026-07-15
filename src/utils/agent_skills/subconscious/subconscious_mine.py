#!/usr/bin/env python3
"""
Tool: Subconscious Miner
Purpose: Mine real user prompts from conversation_history.db to improve the
         subconscious triggers. Scores every user message against the piece
         index using the SAME matching functions as recall (imported — no
         logic divergence) and reports:

         1. Coverage — how many prompts would trigger, per piece
         2. Keyword gaps — prompts semantically near a piece (cosine >= GAP_SIM)
            with zero keyword hits: candidate keyword material, grouped by piece
         3. New-group candidates — prompts far from every piece (max cosine
            < FAR_SIM), greedily clustered; clusters >= MIN_CLUSTER shown
         4. Uncovered frequent n-grams (1-3) across all prompts

         Output is a markdown report for human curation — this tool never
         edits keyword lists itself.

Usage:
    python3 subconscious_mine.py [--db PATH] [--min-len 25] [--since 2026-01-01]
                                 [--out report.md]

Rerun on other machines (e.g. the home desktop's months of history) after
their conversation DB is populated.
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from subconscious_recall import normalize, keyword_hits, cosine, INDEX_PATH  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB = _REPO_ROOT / "database" / "conversation_history.db"

GAP_SIM = 0.63      # "near a piece" — keyword-gap candidates
FAR_SIM = 0.55      # "far from all pieces" — new-group candidates
MIN_CLUSTER = 3     # min prompts to report a new-group cluster
CLUSTER_SIM = 0.72  # mutual cosine for greedy clustering

STOPWORDS = set("""a an and are as at be but by can could did do does for from
has have how i if in is it its just me my no not of on or ok okay so than that
the then there this to u up us was we what when where which will with would you
your can't dont don't i'm im it's lets let's""".split())


def load_prompts(db_path: Path, min_len: int, since: str):
    import sqlite3
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT content, timestamp FROM messages WHERE role='user' "
            "AND timestamp >= ? ORDER BY timestamp", (since,)).fetchall()
    finally:
        conn.close()
    prompts = []
    for content, ts in rows:
        c = (content or "").strip()
        if len(c) < min_len or len(c) > 2000:
            continue
        if c.startswith(("/", "<", "[", "{", "Caveat:")) or "\n```" in c:
            continue
        prompts.append((c, ts))
    return prompts


def ngrams(norm_text: str, n_max: int = 3):
    words = [w for w in norm_text.split() if w not in STOPWORDS and len(w) > 2]
    for n in range(1, n_max + 1):
        for i in range(len(words) - n + 1):
            yield " ".join(words[i:i + n])


def main() -> int:
    ap = argparse.ArgumentParser(description="Mine conversation history for subconscious triggers")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--min-len", type=int, default=25)
    ap.add_argument("--since", default="2000-01-01")
    ap.add_argument("--out", default=None,
                    help="Report path (default: stdout). Reports contain verbatim "
                         "user prompts — keep them OUT of the repo / anywhere committed.")
    args = ap.parse_args()

    if not INDEX_PATH.exists():
        print("No subconscious index — run subconscious_index.py first.")
        return 1
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    pieces = index["pieces"]

    prompts = load_prompts(Path(args.db), args.min_len, args.since)
    if not prompts:
        print("No usable user prompts found.")
        return 1

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "memory"))
    import embed_memory
    model = embed_memory._get_local_model()
    embs = [e.tolist() for e in model.embed([p for p, _ in prompts])]

    all_keywords = {normalize(kw) for p in pieces for kw in p["keywords"]}
    trigger_counts = Counter()
    gaps = defaultdict(list)
    far = []
    triggered = 0

    for (text, ts), emb in zip(prompts, embs):
        norm = normalize(text)
        kw = {p["name"]: keyword_hits(norm, p["keywords"]) for p in pieces}
        sims = {p["name"]: cosine(emb, p["embedding"]) for p in pieces}
        best = max(sims, key=sims.get)
        would = [n for n in kw if kw[n] >= 1] or \
                [n for n, s in sims.items() if s >= 0.70]
        if would:
            triggered += 1
            for n in would:
                trigger_counts[n] += 1
        if not any(kw.values()):
            if sims[best] >= GAP_SIM:
                gaps[best].append((sims[best], text))
            elif sims[best] < FAR_SIM:
                far.append((text, emb))

    # Greedy clustering of far prompts
    clusters = []
    used = set()
    for i, (t, e) in enumerate(far):
        if i in used:
            continue
        group = [(t, i)]
        for j in range(i + 1, len(far)):
            if j not in used and cosine(e, far[j][1]) >= CLUSTER_SIM:
                group.append((far[j][0], j))
        if len(group) >= MIN_CLUSTER:
            used.update(j for _, j in group)
            clusters.append([t for t, _ in group])

    # Frequent uncovered n-grams
    counts = Counter()
    for (text, _) in prompts:
        counts.update(set(ngrams(normalize(text))))
    uncovered = [(g, c) for g, c in counts.most_common(200)
                 if c >= 3 and g not in all_keywords
                 and not any(g in k or k in g for k in all_keywords)][:40]

    lines = [f"# Subconscious mining report",
             f"- prompts analyzed: {len(prompts)} (since {args.since}, min-len {args.min_len})",
             f"- db: {args.db}",
             f"- would trigger: {triggered} ({100*triggered//len(prompts)}%)",
             "", "## Per-piece trigger counts"]
    for p in pieces:
        lines.append(f"- {p['name']}: {trigger_counts.get(p['name'], 0)}")
    lines += ["", "## Keyword gaps (semantic hit, no keyword — candidate phrasings)"]
    for name, items in sorted(gaps.items()):
        lines.append(f"\n### {name}")
        for sim, text in sorted(items, reverse=True)[:8]:
            lines.append(f"- ({sim:.2f}) {text[:160]}")
    lines += ["", f"## New-group candidate clusters (max cosine < {FAR_SIM} to all pieces)"]
    if clusters:
        for i, cl in enumerate(clusters, 1):
            lines.append(f"\n### Cluster {i} ({len(cl)} prompts)")
            for t in cl[:6]:
                lines.append(f"- {t[:160]}")
    else:
        lines.append("(none met the cluster threshold)")
    lines += ["", "## Frequent n-grams not covered by any keyword"]
    for g, c in uncovered:
        lines.append(f"- {g}  ({c}x)")

    report = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"Report -> {args.out}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
