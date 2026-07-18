"""
Tool: Subconscious Autotune (weekly cron + in-session review CLI)
Purpose: Automatically grow the PERSONAL keyword overlay
         (database/memory/subconscious_keywords.json) from real conversation
         history — the automated half of the growth loop. Re-mines user prompts
         the same way subconscious_mine.py does and QUEUES candidate phrases
         passing statistical admission gates into a pending list;
         session_digest.py surfaces the count and the orchestrator proposes
         them to the user (--review / --approve / --reject).

         NOTHING is applied without approval. Statistics alone cannot tell an
         intentful trigger phrase from a content fragment or a typo (a gated
         dry run over 889 real prompts passed junk like "goals projects" and
         "should work" at precision=1.0) — the gates only keep the queue small
         and worth reviewing; judgment does the actual curation.

         Everything it touches is machine-local and gitignored. Generic
         defaults in piece frontmatter are never modified.

QUEUE-ADMISSION GATES (all must pass; tuned against ~900-prompt history):
    SUPPORT   >= 3 prompts contain the phrase, spanning >= 2 sessions
    PRECISION >= 0.6 — of prompts containing the phrase, the fraction
                semantically near the target piece (cosine >= GAP_SIM);
                kills generic words like "project"
    FIRE RATE <  5% of all prompts contain the phrase (spam backstop)
    CAP       pending queue holds at most 10, highest precision first

State (gitignored): database/memory/subconscious_autotune_state.json
    {last_run, pending: [{piece, phrase, support, sessions, precision}],
     applied: [...], rejected: [...]}
Journal: appended to logs/subconscious_autotune.log (also cron's stdout log).

Usage:
    subconscious_autotune.py                # full run (what cron invokes)
    subconscious_autotune.py --dry-run      # full run, nothing written
    subconscious_autotune.py --review       # list pending candidates
    subconscious_autotune.py --approve attack-your-conclusion:"dig into why" ...
    subconscious_autotune.py --reject pre-send-self-test:"wrap this up" ...

Cron (weekly, Sunday 4am — venv python has the embedding backend):
    0 4 * * 0 <repo>/venv/bin/python <this file> >> <repo>/logs/subconscious_autotune.log 2>&1
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from subconscious_recall import normalize, keyword_hits, cosine, INDEX_PATH  # noqa: E402
from subconscious_mine import load_prompts, ngrams, DEFAULT_DB  # noqa: E402
import subconscious_index  # noqa: E402

try:
    from .._common import REPO_ROOT as _REPO_ROOT
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from _common import REPO_ROOT as _REPO_ROOT
STATE_PATH = _REPO_ROOT / "database" / "memory" / "subconscious_autotune_state.json"
OVERLAY_PATH = subconscious_index.KEYWORDS_PATH
JOURNAL_PATH = _REPO_ROOT / "logs" / "subconscious_autotune.log"

GAP_SIM = 0.63          # "near the piece" — same bar as the miner
MIN_SUPPORT = 3         # prompts containing the phrase
MIN_SESSIONS = 2        # distinct sessions among those prompts
MIN_PRECISION = 0.6     # near-piece fraction of phrase-containing prompts
MAX_FIRE_RATE = 0.05    # phrase in more than this fraction of ALL prompts = spam
MAX_PENDING = 10        # queue size cap
PENDING_TTL_DAYS = 28   # unreviewed candidates expire so the queue can't
                        # permanently clog discovery (SIMP-L1-029)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"last_run": None, "pending": [], "applied": [], "rejected": []}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def journal(line: str) -> None:
    JOURNAL_PATH.parent.mkdir(exist_ok=True)
    with JOURNAL_PATH.open("a", encoding="utf-8") as f:
        f.write(f"[{_now()}] {line}\n")


def load_overlay() -> dict:
    if OVERLAY_PATH.exists():
        return json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))
    return {}


def apply_to_overlay(items: list) -> None:
    """items: [{piece, phrase, ...}] — extend overlay + rebuild index."""
    overlay = load_overlay()
    for it in items:
        overlay.setdefault(it["piece"], [])
        if it["phrase"] not in overlay[it["piece"]]:
            overlay[it["piece"]].append(it["phrase"])
    OVERLAY_PATH.write_text(json.dumps(overlay, indent=2) + "\n", encoding="utf-8")
    subconscious_index.build_index()


def _known_phrases(state: dict) -> set:
    """Normalized (piece, phrase) pairs already applied/pending/rejected."""
    return {(it["piece"], normalize(it["phrase"]))
            for key in ("pending", "applied", "rejected", "expired")
            for it in state.get(key, [])}


def _covered(phrase_norm: str, existing_norm: list) -> bool:
    """Substring-overlap rule (same spirit as the miner's uncovered check)."""
    return any(phrase_norm in k or k in phrase_norm for k in existing_norm)


def mine_candidates(state: dict):
    """Returns (queued, n_prompts). Pure analysis — no writes."""
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    pieces = index["pieces"]
    prompts = load_prompts(DEFAULT_DB, min_len=25, since="2000-01-01")
    if not prompts:
        return [], [], 0

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "memory"))
    import embed_memory
    model = embed_memory._get_local_model()
    embs = [e.tolist() for e in model.embed([p for p, *_ in prompts])]

    norm_prompts = [(normalize(text), sid) for text, _, sid in prompts]
    known = _known_phrases(state)
    existing_norm = [normalize(kw) for p in pieces for kw in p["keywords"]]

    # Gap prompts per piece: semantically near, zero keyword hits.
    gap_idx = {p["name"]: [] for p in pieces}
    for i, ((text, _, _), emb) in enumerate(zip(prompts, embs)):
        norm = norm_prompts[i][0]
        for p in pieces:
            if cosine(emb, p["embedding"]) >= GAP_SIM and keyword_hits(norm, p["keywords"]) == 0:
                gap_idx[p["name"]].append(i)

    candidates = []
    for p in pieces:
        name = p["name"]
        seen_grams = set()
        for i in gap_idx[name]:
            for g in ngrams(norm_prompts[i][0]):
                if len(g.split()) < 2 or g in seen_grams:
                    continue  # single words are too noisy to auto-add
                seen_grams.add(g)
                if (name, g) in known or _covered(g, existing_norm):
                    continue
                hit_ids = [j for j, (npr, _) in enumerate(norm_prompts) if g in npr]
                support = len(hit_ids)
                if support < MIN_SUPPORT:
                    continue
                sessions = len({norm_prompts[j][1] for j in hit_ids})
                near = sum(1 for j in hit_ids
                           if cosine(embs[j], p["embedding"]) >= GAP_SIM)
                precision = near / support
                fire_rate = support / len(prompts)
                candidates.append({
                    "piece": name, "phrase": g, "support": support,
                    "sessions": sessions, "precision": round(precision, 2),
                    "fire_rate": round(fire_rate, 3),
                })

    queued = []
    for c in sorted(candidates, key=lambda c: -c["precision"]):
        if (c["support"] >= MIN_SUPPORT and c["sessions"] >= MIN_SESSIONS
                and c["precision"] >= MIN_PRECISION and c["fire_rate"] < MAX_FIRE_RATE):
            queued.append(c)
    return queued[:max(0, MAX_PENDING - len(state["pending"]))], len(prompts)


def _expire_pending(state: dict) -> int:
    """Drop pending candidates older than PENDING_TTL_DAYS. Legacy items with
    no queued_at get stamped now and start aging from today. Expired items are
    journaled and moved to state['expired'] (kept so they never re-queue)."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=PENDING_TTL_DAYS)
    kept, expired = [], []
    for c in state["pending"]:
        if not c.get("queued_at"):
            c["queued_at"] = _now()
        ts = datetime.fromisoformat(c["queued_at"])
        (expired if ts < cutoff else kept).append(c)
    if expired:
        for c in expired:
            c["expired_at"] = _now()
            journal(f"EXPIRE {c['piece']}: \"{c['phrase']}\" (queued {c['queued_at']})")
        state.setdefault("expired", []).extend(expired)
        state["pending"] = kept
    return len(expired)


def run(dry_run: bool = False) -> int:
    state = load_state()
    n_expired = _expire_pending(state)
    if n_expired:
        print(f"EXPIRED {n_expired} stale pending candidate(s) (> {PENDING_TTL_DAYS}d unreviewed)")
    queued, n = mine_candidates(state)
    for c in queued:
        c["queued_at"] = _now()
    for c in queued:
        print(f"QUEUE {c['piece']}: \"{c['phrase']}\" "
              f"(support={c['support']}, sessions={c['sessions']}, "
              f"precision={c['precision']}, fire_rate={c['fire_rate']})")
    summary = (f"run over {n} prompts: {len(queued)} queued for review, "
               f"{len(state['pending'])} already pending")
    print(summary)
    if dry_run:
        print("DRY RUN — nothing written.")
        return 0

    for c in queued:
        journal(f"QUEUE {c['piece']}: \"{c['phrase']}\" {c}")
    state["pending"].extend(queued)
    state["last_run"] = _now()
    state["last_run_summary"] = summary
    state["last_run_error"] = None
    save_state(state)
    return 0


def review() -> int:
    state = load_state()
    if not state["pending"]:
        print("No pending candidates.")
        return 0
    print(f"{len(state['pending'])} pending candidate(s):")
    for c in state["pending"]:
        print(f"  {c['piece']}:\"{c['phrase']}\"  support={c['support']} "
              f"sessions={c['sessions']} precision={c['precision']} "
              f"fire_rate={c['fire_rate']}")
    print("\nResolve with --approve/--reject piece:\"phrase\" [...]")
    return 0


def resolve(specs: list, approve: bool) -> int:
    state = load_state()
    wanted = set()
    for spec in specs:
        piece, _, phrase = spec.partition(":")
        wanted.add((piece.strip(), normalize(phrase)))
    matched = [c for c in state["pending"]
               if (c["piece"], normalize(c["phrase"])) in wanted]
    if len(matched) != len(wanted):
        found = {(c["piece"], normalize(c["phrase"])) for c in matched}
        for miss in wanted - found:
            print(f"ERROR: not in pending queue: {miss[0]}:\"{miss[1]}\"")
        return 1
    state["pending"] = [c for c in state["pending"] if c not in matched]
    verdict = "APPROVE" if approve else "REJECT"
    if approve:
        apply_to_overlay(matched)
        for c in matched:
            c["applied_at"] = _now()
        state["applied"].extend(matched)
    else:
        for c in matched:
            c["rejected_at"] = _now()
        state["rejected"].extend(matched)
    for c in matched:
        journal(f"{verdict} {c['piece']}: \"{c['phrase']}\"")
        print(f"{verdict} {c['piece']}: \"{c['phrase']}\"")
    save_state(state)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Gated automatic keyword tuning for the subconscious")
    ap.add_argument("--dry-run", action="store_true", help="Analyze + print, write nothing")
    ap.add_argument("--review", action="store_true", help="List pending candidates")
    ap.add_argument("--approve", nargs="+", metavar='PIECE:"PHRASE"', help="Approve pending candidates")
    ap.add_argument("--reject", nargs="+", metavar='PIECE:"PHRASE"', help="Reject pending candidates")
    args = ap.parse_args()
    try:
        if args.review:
            sys.exit(review())
        elif args.approve:
            sys.exit(resolve(args.approve, approve=True))
        elif args.reject:
            sys.exit(resolve(args.reject, approve=False))
        sys.exit(run(dry_run=args.dry_run))
    except Exception as e:  # cron half is fail-open, like recall
        print(f"ERROR (fail-open): {e}", file=sys.stderr)
        if not (args.approve or args.reject or args.review):
            # Record the cron failure so session_digest surfaces it instead of
            # it dying silently in the cron log (SIMP-L1-029).
            try:
                state = load_state()
                state["last_run_error"] = {"at": _now(), "error": str(e)[:300]}
                save_state(state)
            except Exception:
                pass
        sys.exit(0 if not (args.approve or args.reject) else 1)
