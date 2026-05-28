"""
Qualitative trial inspection.

Companion to analyze.py. Where analyze.py gives you aggregate numbers,
inspect_trials.py shows you the actual chain-of-thought and recall text
for the most interesting individual trials.

Use cases:
  - "Show me what models said in the trials they violated on."
  - "Show me cases where the recall-probe LLM-judge had to rescue a paraphrased recall."
  - "Show me cases where the 3-judge hallucination-type ensemble disagreed."
  - "Show me the agent's reasoning when it landed in the HIUA-candidate cell."

Usage:
    python inspect_trials.py <jsonl_file> [--mode MODE] [--n N] [--model MODEL]

Modes:
  violations    Top N violations (any kind), sorted by item difficulty
  hiua          Trials in the HIUA-candidate cell (violation + recalled + hallucinated)
  kbv           Trials in the KBV cell (violation + recalled + no hallucination)
  recall_judge  Trials where the LLM-judge had to rescue the recall (paraphrased)
  disagreement  Trials where the 3-judge hallucination ensemble disagreed
  errors        Trials that errored out (for debugging)
  random        N random trials regardless of cell
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def load(path: str) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def truncate(text: str, max_len: int = 1500) -> str:
    """Truncate long responses with a clear marker."""
    if not text:
        return "<empty>"
    if len(text) <= max_len:
        return text
    head = text[: max_len // 2]
    tail = text[-(max_len // 2) :]
    return f"{head}\n  ... [{len(text) - max_len} chars truncated] ...\n{tail}"


def print_trial(row: dict, idx: int, show_full: bool = False) -> None:
    """Print one trial in a human-inspectable format."""
    print("=" * 80)
    print(f"TRIAL {idx}")
    print(f"  item_id        {row.get('item_id')}")
    print(f"  model          {row.get('model_id')}  (provider={row.get('provider')}, tier={row.get('tier')})")
    print(f"  sub_construct  {row.get('sub_construct')}")
    print(f"  domain         {row.get('domain')}")
    print(f"  salience       {row.get('salience')}")
    print(f"  seed           {row.get('seed')}")
    print()
    print(f"  hiua_cell      {row.get('hiua_cell')}")
    print(f"  forbidden_taken {row.get('forbidden_action_taken')}   compliant_taken {row.get('compliant_action_taken')}")
    print(f"  recall_correct  {row.get('recall_correct')}")
    print(f"  score_method    {row.get('score_method')}")
    print(f"  recall_method   {row.get('recall_method', 'N/A')}")
    if row.get("judge_majority"):
        print(f"  judge_majority  {row['judge_majority']}    judge_agreement {row.get('judge_agreement')}")
        if row.get("judge_labels"):
            print(f"  judge_labels    {row['judge_labels']}")
    if row.get("error"):
        print(f"  ERROR          {row['error'][:300]}")

    print()
    print("-" * 4 + " parsed action " + "-" * 60)
    print(f"  {row.get('parsed_action') or '<no ACTION line parsed>'}")

    print()
    print("-" * 4 + " action response (full chain-of-thought) " + "-" * 35)
    print(truncate(row.get("action_response", ""), max_len=3000 if show_full else 1500))

    print()
    print("-" * 4 + " recall response " + "-" * 58)
    print(truncate(row.get("recall_response", ""), max_len=2000 if show_full else 800))
    print()


# --------------------------------------------------------------------------
# Mode selectors
# --------------------------------------------------------------------------

def mode_violations(rows: list[dict], n: int) -> list[dict]:
    """All trials where the agent took a forbidden action. Sorted by item difficulty
    (items with highest per-item violation rates first) so the most diagnostic
    cases appear at the top."""
    viols = [r for r in rows if r.get("forbidden_action_taken")]
    # Rank items by per-item violation rate (proxy for difficulty)
    by_item: dict[str, list[dict]] = {}
    for r in rows:
        by_item.setdefault(r["item_id"], []).append(r)
    item_violation_rate = {
        k: sum(1 for r in v if r.get("forbidden_action_taken")) / len(v)
        for k, v in by_item.items()
    }
    viols.sort(key=lambda r: (-item_violation_rate[r["item_id"]], r["item_id"]))
    return viols[:n]


def mode_hiua(rows: list[dict], n: int) -> list[dict]:
    """HIUA-candidate cell: forbidden action + recalled rule + judge says hallucination.
    If no judge labels (pre-judge JSONL), falls back to 'violation_not_recalled' cell."""
    halluc_types = {"authorization", "state", "tool"}
    with_judges = [
        r for r in rows
        if r.get("forbidden_action_taken")
        and r.get("recall_correct")
        and r.get("judge_majority") in halluc_types
    ]
    if with_judges:
        return with_judges[:n]
    # Pre-judge fallback
    return [r for r in rows if r.get("hiua_cell") == "violation_not_recalled"][:n]


def mode_kbv(rows: list[dict], n: int) -> list[dict]:
    """Knows-but-violates: forbidden + recalled + no hallucination."""
    with_judges = [
        r for r in rows
        if r.get("forbidden_action_taken")
        and r.get("recall_correct")
        and r.get("judge_majority") == "none"
    ]
    if with_judges:
        return with_judges[:n]
    return [r for r in rows if r.get("hiua_cell") == "violation_recalled"][:n]


def mode_recall_judge(rows: list[dict], n: int) -> list[dict]:
    """Trials where the substring scorer missed the recall but the LLM-judge rescued it.
    These are the paraphrased-recall cases. The whole 'substantive validity' argument
    leans on the judge fallback being meaningful, so reading these is load-bearing."""
    return [r for r in rows if r.get("recall_method") == "judge_yes"][:n]


def mode_disagreement(rows: list[dict], n: int) -> list[dict]:
    """Trials where the 3-judge hallucination ensemble didn't unanimously agree.
    These are the borderline cases that show what's actually hard about labeling."""
    disagreements = [r for r in rows if r.get("judge_labels") and not r.get("judge_agreement", True)]
    return disagreements[:n]


def mode_errors(rows: list[dict], n: int) -> list[dict]:
    """Trials that errored out. For debugging API issues, model deprecation, etc."""
    return [r for r in rows if r.get("error")][:n]


def mode_random(rows: list[dict], n: int) -> list[dict]:
    """N random trials regardless of cell. Useful for spot-checking."""
    clean = [r for r in rows if not r.get("error")]
    return random.sample(clean, min(n, len(clean)))


MODE_FNS = {
    "violations":   mode_violations,
    "hiua":         mode_hiua,
    "kbv":          mode_kbv,
    "recall_judge": mode_recall_judge,
    "disagreement": mode_disagreement,
    "errors":       mode_errors,
    "random":       mode_random,
}


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl_path")
    ap.add_argument("--mode", choices=list(MODE_FNS), default="violations")
    ap.add_argument("--n", type=int, default=5, help="how many trials to show")
    ap.add_argument("--model", default=None, help="filter to one model_id")
    ap.add_argument("--item", default=None, help="filter to one item_id")
    ap.add_argument("--full", action="store_true", help="show full untruncated responses")
    ap.add_argument("--summary-only", action="store_true",
                    help="print a one-line summary per trial instead of full transcripts")
    args = ap.parse_args()

    rows = load(args.jsonl_path)
    print(f"Loaded {len(rows)} rows from {args.jsonl_path}")

    if args.model:
        rows = [r for r in rows if r.get("model_id") == args.model]
        print(f"  filtered to model={args.model}: {len(rows)} rows")
    if args.item:
        rows = [r for r in rows if r.get("item_id") == args.item]
        print(f"  filtered to item={args.item}: {len(rows)} rows")

    selected = MODE_FNS[args.mode](rows, args.n)
    print(f"\nMode '{args.mode}' selected {len(selected)} trials.\n")

    if args.summary_only:
        for i, r in enumerate(selected, 1):
            action = (r.get("parsed_action") or "<no ACTION>")[:80]
            cell = r.get("hiua_cell", "?")
            judge = r.get("judge_majority", "")
            print(f"  {i:2d}. [{r.get('model_id'):<22}] {r.get('item_id'):<30} cell={cell:<24} judge={judge:<14} action={action}")
        return

    for i, r in enumerate(selected, 1):
        print_trial(r, i, show_full=args.full)


if __name__ == "__main__":
    main()
