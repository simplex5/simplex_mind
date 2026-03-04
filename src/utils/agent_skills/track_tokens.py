#!/usr/bin/env python3
"""
track_tokens.py — Count tokens for agent calls and append call objects to metrics JSON.

Modes:
  --claude-delta:
    Read /tmp/claude_session_state.json (written by statusline.sh after every Claude
    response) and compute deltas from /tmp/claude_session_prev_state.json. Reports
    exact Anthropic API token counts — no (est.) suffix.

  --lmstudio-log:
    Parse /tmp/lmstudio_log_stream.jsonl for the most recent llm.prediction.output
    entry's token counts. Reports exact integers from the inference engine.

Usage (claude-delta):
    python src/utils/agent_skills/track_tokens.py \
        --claude-delta \
        --agent Claude \
        --seq 0 \
        --phase "session-start — orchestration" \
        --file metrics/2026-01-01_12-00.json

Usage (lmstudio-log):
    python src/utils/agent_skills/track_tokens.py \
        --lmstudio-log \
        --agent "LM Studio" \
        --seq 1 \
        --phase "index.html — code" \
        --file metrics/2026-01-01_12-00.json

Usage (direct):
    python src/utils/agent_skills/track_tokens.py \
        --direct \
        --tokens-prompt 150 \
        --tokens-response 420 \
        --model flash \
        --agent Gemini \
        --seq 2 \
        --phase "index.html — review-1" \
        --file metrics/2026-01-01_12-00.json

NOTE: The --claude-delta mode depends on statusline.sh writing session state files.
      This is an optional feature — see README for details.
"""

import argparse
import json
import sys
from pathlib import Path

SESSION_STATE_PATH = Path("/tmp/claude_session_state.json")
SESSION_PREV_PATH  = Path("/tmp/claude_session_prev_state.json")
LMSTUDIO_LOG_PATH  = Path("/tmp/lmstudio_log_stream.jsonl")


def read_session_counts(path: Path) -> dict:
    """Returns dict with input, cache_creation, cache_read, output, cost fields."""
    if not path.exists():
        return {"input": 0, "cache_creation": 0, "cache_read": 0, "output": 0, "cost": 0.0}
    raw = json.loads(path.read_text())
    cw = raw.get("context_window", {}).get("current_usage", {})
    return {
        "input":          cw.get("input_tokens", 0),
        "cache_creation": cw.get("cache_creation_input_tokens", 0),
        "cache_read":     cw.get("cache_read_input_tokens", 0),
        "output":         cw.get("output_tokens", 0),
        "cost":           raw.get("cost", {}).get("total_cost_usd", 0.0),
    }


def read_lmstudio_log() -> tuple[int, int, str]:
    """Parse the last llm.prediction.output entry from the log stream.
    Returns (prompt_tokens, completion_tokens, model_identifier).
    Errors out if file missing or no valid entry found."""
    if not LMSTUDIO_LOG_PATH.exists():
        print(f"  [track_tokens] ERROR: {LMSTUDIO_LOG_PATH} not found. "
              "Is the log stream running?", file=sys.stderr)
        sys.exit(1)

    text = LMSTUDIO_LOG_PATH.read_text().strip()
    if not text:
        print(f"  [track_tokens] ERROR: {LMSTUDIO_LOG_PATH} is empty. "
              "No inference calls logged yet.", file=sys.stderr)
        sys.exit(1)

    # Walk lines in reverse to find the last prediction.output entry
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        data = entry.get("data", {})
        if data.get("type") != "llm.prediction.output":
            continue
        stats = data.get("stats", {})
        prompt_tokens = stats.get("promptTokensCount", 0)
        completion_tokens = stats.get("predictedTokensCount", 0)
        model_id = data.get("modelIdentifier", "unknown")
        return prompt_tokens, completion_tokens, model_id

    print(f"  [track_tokens] ERROR: No llm.prediction.output entry found in "
          f"{LMSTUDIO_LOG_PATH}", file=sys.stderr)
    sys.exit(1)


def load_metrics(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {"run_id": path.stem, "calls": [], "summary": {}}


def save_metrics(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Append an agent call object to metrics JSON.")
    parser.add_argument("--claude-delta", action="store_true",
                        help="Read exact token counts from statusline session state files")
    parser.add_argument("--lmstudio-log", action="store_true",
                        help="Parse LM Studio log stream for exact token counts")
    parser.add_argument("--direct", action="store_true",
                        help="Record direct token counts (any provider that returns counts directly)")
    parser.add_argument("--tokens-prompt", type=int, default=0,
                        help="Prompt token count (optional with --direct, default 0)")
    parser.add_argument("--tokens-response", type=int,
                        help="Response token count (required with --direct)")
    parser.add_argument("--model", default="",
                        help="Model identifier (used with --direct, e.g. 'flash' or 'pro')")
    parser.add_argument("--agent", default="Claude", help="Agent name (Claude/Gemini/LM Studio)")
    parser.add_argument("--seq", type=int, required=True, help="Sequence number")
    parser.add_argument("--file", required=True, help="Path to metrics JSON file")
    parser.add_argument("--phase", default="", help="Phase label")
    parser.add_argument("--fix-cycle", type=int, default=0, help="Fix cycle count")
    parser.add_argument("--notes", default="", help="Freeform notes")
    args = parser.parse_args()

    if not args.claude_delta and not args.lmstudio_log and not args.direct:
        parser.error("One of --claude-delta, --lmstudio-log, or --direct is required")

    if args.direct:
        if args.tokens_response is None:
            parser.error("--tokens-response is required with --direct")

    phase = args.phase or f"seq{args.seq} — {args.agent.lower()}"

    if args.claude_delta:
        current = read_session_counts(SESSION_STATE_PATH)
        prev    = read_session_counts(SESSION_PREV_PATH)

        input_delta    = current["input"]          - prev["input"]
        cache_cr_delta = current["cache_creation"] - prev["cache_creation"]
        cache_rd_delta = current["cache_read"]     - prev["cache_read"]
        output_delta   = current["output"]         - prev["output"]
        cost_delta     = current["cost"]           - prev["cost"]

        prompt_total = input_delta + cache_cr_delta + cache_rd_delta

        # Advance baseline for next delta
        SESSION_PREV_PATH.write_text(SESSION_STATE_PATH.read_text())

        notes_parts = [
            f"input={input_delta} cache_cr={cache_cr_delta} cache_rd={cache_rd_delta}",
            f"| ${cost_delta:.4f}",
        ]
        if args.notes:
            notes_parts.append(f"| {args.notes}")
        notes_str = " ".join(notes_parts)

        call_obj = {
            "seq": args.seq,
            "phase": phase,
            "agent": args.agent,
            "model": "claude-sonnet-4-6",
            "tokens_prompt": str(prompt_total),
            "tokens_response": str(output_delta),
            "fix_cycle": args.fix_cycle,
            "notes": notes_str,
        }

        print(
            f"  [track_tokens] seq={args.seq} agent={args.agent} "
            f"prompt={prompt_total} response={output_delta} cost_delta=${cost_delta:.4f} "
            f"[exact from Anthropic API]"
        )

    elif args.lmstudio_log:
        prompt_tokens, completion_tokens, model_id = read_lmstudio_log()

        notes_str = "from log stream"
        if args.notes:
            notes_str += f" | {args.notes}"

        call_obj = {
            "seq": args.seq,
            "phase": phase,
            "agent": args.agent,
            "model": model_id,
            "tokens_prompt": str(prompt_tokens),
            "tokens_response": str(completion_tokens),
            "fix_cycle": args.fix_cycle,
            "notes": notes_str,
        }

        print(
            f"  [track_tokens] seq={args.seq} agent={args.agent} "
            f"prompt={prompt_tokens} response={completion_tokens} "
            f"model={model_id} [exact from log stream]"
        )

    elif args.direct:
        model_id = args.model or "flash"


        if args.tokens_prompt == 0:
            notes_str = "prompt count skipped — response only | direct token count"
        else:
            notes_str = "direct token count"
        if args.notes:
            notes_str += f" | {args.notes}"

        call_obj = {
            "seq": args.seq,
            "phase": phase,
            "agent": args.agent,
            "model": model_id,
            "tokens_prompt": str(args.tokens_prompt),
            "tokens_response": str(args.tokens_response),
            "fix_cycle": args.fix_cycle,
            "notes": notes_str,
        }

        print(
            f"  [track_tokens] seq={args.seq} agent={args.agent} "
            f"prompt={args.tokens_prompt} response={args.tokens_response} "
            f"model={model_id} [direct token count]"
        )

    metrics_path = Path(args.file)
    data = load_metrics(metrics_path)

    existing = [c for c in data["calls"] if c.get("seq") != args.seq]
    existing.append(call_obj)
    existing.sort(key=lambda c: c["seq"])
    data["calls"] = existing

    save_metrics(metrics_path, data)


if __name__ == "__main__":
    main()
