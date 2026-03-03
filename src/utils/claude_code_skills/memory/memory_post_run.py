"""
Tool: memory_post_run.py
Purpose: Post-run memory writer — reads a metrics JSON and writes structured
         memory entries + anomaly tickets to the database.

Called at the end of each successful run by an orchestrator or CI pipeline.

Usage:
    python src/utils/claude_code_skills/memory/memory_post_run.py \
      --metrics-file output/metrics/2026-02-25_03-11.json \
      --anomaly-threshold 4

Actions:
    1. Write end-of-run insight entry (always)
    2. Create bug ticket if any file has fix_cycles > threshold
    3. Upsert model-performance fact entry with rolling average

Output:
    JSON result with success status and list of actions taken
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Path bootstrap ─────────────────────────────────────────────────────────────
_SCRIPT_DIR   = Path(__file__).parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent.parent.parent.parent

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── Memory / ticket imports ───────────────────────────────────────────────────
try:
    from src.utils.claude_code_skills.memory.memory_db import (
        add_entry,
        search_entries,
        update_entry,
    )
except ImportError:
    sys.path.insert(0, str(_SCRIPT_DIR))
    from memory_db import add_entry, search_entries, update_entry

try:
    from src.utils.claude_code_skills.tickets.ticket_db import (
        create_ticket,
        list_tickets,
        update_ticket,
    )
except ImportError:
    sys.path.insert(0, str(_SCRIPT_DIR.parent / "tickets"))
    from ticket_db import create_ticket, list_tickets, update_ticket


# ── Helpers ───────────────────────────────────────────────────────────────────

def _model_label(run_config: dict) -> str:
    """Return a short, human-readable model label from run_config."""
    coder = run_config.get("lm_model") or run_config.get("coder_model", "unknown")
    # Strip provider prefix (e.g. "gemini:gemini-3.1-pro-preview" → "gemini-3.1-pro-preview")
    if ":" in coder:
        coder = coder.split(":", 1)[1]
    return coder


def _project_label(run_config: dict) -> str:
    """Extract project name from prd_file path."""
    prd = run_config.get("prd_file", "")
    m = re.search(r"projects[/\\]([^/\\]+)[/\\]", prd)
    return m.group(1) if m else "unknown"


def _write_run_insight(summary: dict) -> Dict[str, Any]:
    """Write a single insight entry summarising the completed run."""
    run_id   = summary.get("run_id", "unknown")
    config   = summary.get("run_config", {})
    model    = _model_label(config)
    project  = _project_label(config)
    n_files  = len(summary.get("files_delivered", []))
    cycles   = summary.get("fix_cycles_per_file", {})
    wall     = summary.get("wall_clock_seconds", 0)
    fallback = summary.get("reviewer_fallback_count", 0)
    ratio    = summary.get("claude_token_ratio")

    cycles_str = " ".join(f"{f}={c}" for f, c in cycles.items())
    ratio_str  = str(ratio) if ratio is not None else "null"

    content = (
        f"Run {run_id} | {project} | {model} | {n_files} files | "
        f"fix_cycles: {cycles_str} | wall={wall}s | "
        f"fallbacks={fallback} | ratio={ratio_str}"
    )

    return add_entry(
        content=content,
        entry_type="insight",
        source="system",
        importance=6,
        tags=["run", "metrics", project, model],
        context=run_id,
    )


def _check_anomalies(summary: dict, threshold: int) -> List[Dict[str, Any]]:
    """Create bug tickets for any file with fix_cycles > threshold.

    Deduplicates: if an open ticket already mentions the same filename,
    appends a note to the existing ticket instead of creating a new one.
    """
    config   = summary.get("run_config", {})
    model    = _model_label(config)
    project  = _project_label(config)
    run_id   = summary.get("run_id", "unknown")
    cycles   = summary.get("fix_cycles_per_file", {})

    # Pre-fetch open bug tickets once for dedup lookup
    open_tickets = []
    try:
        ticket_result = list_tickets(status="open", ticket_type="bug", project=project)
        if ticket_result.get("success"):
            open_tickets = ticket_result.get("tickets", [])
    except Exception:
        pass  # If list fails, fall through to create new tickets

    results = []
    for filename, count in cycles.items():
        if count > threshold:
            # Check for existing open ticket mentioning this filename
            existing = None
            for t in open_tickets:
                if filename in (t.get("title") or ""):
                    existing = t
                    break

            if existing:
                # Append a note to the existing ticket
                old_notes = existing.get("notes") or ""
                new_note = (
                    f"\n[{run_id}] {count} fix cycles (model: {model})"
                )
                result = update_ticket(
                    existing["id"],
                    notes=(old_notes + new_note).strip(),
                )
                results.append({"file": filename, "cycles": count, "ticket": result, "action": "updated"})
            else:
                result = create_ticket(
                    ticket_type="bug",
                    title=f"High fix-cycle count: {filename} ({count} cycles) [{run_id}]",
                    description=(
                        f"File '{filename}' required {count} fix cycles (threshold={threshold}) "
                        f"during run {run_id}. Model: {model}. "
                        f"Investigate whether the prompt, spec, or model output is causing repeated failures."
                    ),
                    project=project,
                    how_discovered=f"auto-detected by memory_post_run.py during run {run_id}",
                    priority="high" if count > threshold * 2 else "medium",
                )
                results.append({"file": filename, "cycles": count, "ticket": result, "action": "created"})
    return results


def _upsert_model_performance(summary: dict) -> Dict[str, Any]:
    """
    Update (or create) a rolling-average model-performance fact entry.

    Searches for an existing entry tagged ["model-performance", model, project].
    If found: parses the avg and run count, computes new average, updates content.
    If not found: creates a new entry.

    Rolling average formula: new_avg = (old_avg * old_n + new_value) / (old_n + 1)
    """
    config  = summary.get("run_config", {})
    model   = _model_label(config)
    project = _project_label(config)
    cycles  = summary.get("fix_cycles_per_file", {})

    if not cycles:
        return {"success": True, "skipped": True, "reason": "no fix_cycle data"}

    values    = list(cycles.values())
    new_avg   = sum(values) / len(values)
    new_best  = min(values)
    new_worst = max(values)

    tag_string = json.dumps(["model-performance", model, project])

    # Search for an existing entry by tag content match
    search_result = search_entries(
        query=f"Model {model} on {project}",
        entry_type="fact",
        limit=10,
    )

    existing_entry = None
    if search_result.get("success"):
        for e in search_result.get("entries", []):
            tags_raw = e.get("tags", "[]") or "[]"
            try:
                tags = json.loads(tags_raw)
            except (json.JSONDecodeError, TypeError):
                tags = []
            if "model-performance" in tags and model in tags and project in tags:
                existing_entry = e
                break

    if existing_entry:
        # Parse existing stats from content
        content = existing_entry.get("content", "")
        n_match  = re.search(r"over (\d+) runs?", content)
        av_match = re.search(r"avg ([0-9.]+) fix_cycles", content)
        b_match  = re.search(r"best: ([0-9]+)", content)
        w_match  = re.search(r"worst: ([0-9]+)", content)

        old_n    = int(n_match.group(1))   if n_match  else 1
        old_avg  = float(av_match.group(1)) if av_match else new_avg
        old_best = int(b_match.group(1))   if b_match  else new_best
        old_worst= int(w_match.group(1))   if w_match  else new_worst

        updated_n    = old_n + 1
        updated_avg  = round((old_avg * old_n + new_avg) / updated_n, 2)
        updated_best = min(old_best, new_best)
        updated_worst= max(old_worst, new_worst)

        new_content = (
            f"Model {model} on {project}: avg {updated_avg} fix_cycles/file "
            f"over {updated_n} runs (best: {updated_best}, worst: {updated_worst})"
        )
        return update_entry(
            existing_entry["id"],
            content=new_content,
            importance=7,
        )
    else:
        avg_rounded = round(new_avg, 2)
        content = (
            f"Model {model} on {project}: avg {avg_rounded} fix_cycles/file "
            f"over 1 run (best: {new_best}, worst: {new_worst})"
        )
        return add_entry(
            content=content,
            entry_type="fact",
            source="inferred",
            importance=7,
            tags=["model-performance", model, project],
            context=f"First run recorded: {summary.get('run_id', 'unknown')}",
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def run(metrics_file: str, anomaly_threshold: int = 4) -> Dict[str, Any]:
    """
    Main entry point. Returns a dict describing all actions taken.

    Args:
        metrics_file: Path to the metrics JSON file written by the orchestrator.
        anomaly_threshold: Fix-cycle count above which a bug ticket is created.
    """
    mp = Path(metrics_file)
    if not mp.exists():
        return {"success": False, "error": f"Metrics file not found: {metrics_file}"}

    try:
        data = json.loads(mp.read_text())
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Failed to parse metrics JSON: {e}"}

    summary = data.get("summary", {})
    if not summary:
        return {"success": False, "error": "metrics JSON has no 'summary' block"}

    actions: Dict[str, Any] = {"metrics_file": metrics_file}

    # 1. End-of-run insight
    insight_result = _write_run_insight(summary)
    actions["insight"] = insight_result

    # 2. Anomaly tickets
    anomaly_results = _check_anomalies(summary, anomaly_threshold)
    actions["anomaly_tickets"] = anomaly_results

    # 3. Model performance rolling average
    perf_result = _upsert_model_performance(summary)
    actions["model_performance"] = perf_result

    actions["success"] = True
    return actions


def main():
    parser = argparse.ArgumentParser(
        description="Post-run memory writer — read metrics JSON, write memory + tickets"
    )
    parser.add_argument(
        "--metrics-file", required=True,
        help="Path to the metrics JSON file written by the orchestrator"
    )
    parser.add_argument(
        "--anomaly-threshold", type=int, default=4,
        help="Fix-cycle count above which a bug ticket is auto-created (default: 4)"
    )
    args = parser.parse_args()

    result = run(args.metrics_file, args.anomaly_threshold)

    if result.get("success"):
        insight = result.get("insight", {})
        tickets = result.get("anomaly_tickets", [])
        perf    = result.get("model_performance", {})

        insight_ok = insight.get("success", False)
        perf_ok    = perf.get("success", False)

        # Insight might be a duplicate (same run_id re-processed) — that's fine
        insight_status = "written" if insight_ok else (
            "duplicate (skipped)" if "Duplicate" in insight.get("error", "") else "FAILED"
        )
        ticket_ids = [t["ticket"].get("id", "?") for t in tickets if t.get("ticket", {}).get("success")]
        perf_status = "updated" if (perf_ok and "updated" in perf.get("message", "")) else (
            "created" if perf_ok else "FAILED"
        )

        print(f"OK insight={insight_status} tickets={ticket_ids or 'none'} performance={perf_status}")
    else:
        print(f"ERROR {result.get('error', 'unknown error')}")
        sys.exit(1)

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
