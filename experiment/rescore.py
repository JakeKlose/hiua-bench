"""
Re-score an existing trial JSONL with the current score_action / score_recall logic.

Use case: we ran dev_groq, then patched the scoring parser (e.g. to handle gpt-oss
Harmony format). Rather than burn another ~20 min on a fresh Modal run, we re-score
the stored action_response / recall_response fields against the patched logic.

This intentionally does NOT call the LLM judge fallback — we want a pure
local-logic re-score. Rows that were originally `judge_resolved` keep their stored
verdict; rows that flip from one regex-decided cell to another get re-classified.

Usage:
    python3 rescore.py run_xxx.jsonl --out run_xxx_rescored.jsonl
    python3 rescore.py run_xxx.jsonl --in-place        # overwrite, with .bak backup
    python3 rescore.py run_xxx.jsonl --diff-only       # print what changed, don't write
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

# We import the patched scorers directly from modal_app. score_action /
# score_recall are pure string-processing functions, but modal_app imports
# `modal` at module top level which we don't need here. Stub it.
sys.path.insert(0, str(Path(__file__).parent))
import types as _types
if "modal" not in sys.modules:
    _stub = _types.ModuleType("modal")
    # The decorators in modal_app are used at module load time. Stub each
    # one to return its argument unchanged (or a passthrough callable).
    class _PassthroughDecorator:
        def __call__(self, *a, **k):
            # Used as @decorator or @decorator(...)
            if a and callable(a[0]) and not k:
                return a[0]
            def _wrap(fn):
                return fn
            return _wrap
    _stub.App = lambda *a, **k: _types.SimpleNamespace(
        function=_PassthroughDecorator(), cls=_PassthroughDecorator(),
        local_entrypoint=_PassthroughDecorator(),
    )
    _stub.Image = _types.SimpleNamespace(debian_slim=lambda *a, **k: _types.SimpleNamespace(
        pip_install=lambda *a, **k: _types.SimpleNamespace(
            add_local_python_source=lambda *a, **k: None,
            add_local_file=lambda *a, **k: None,
        ),
    ))
    _stub.Volume = _types.SimpleNamespace(from_name=lambda *a, **k: None)
    _stub.Secret = _types.SimpleNamespace(from_name=lambda *a, **k: None)
    _stub.Cls = _types.SimpleNamespace(from_name=lambda *a, **k: None)
    _stub.parameter = lambda *a, **k: None
    _stub.enter = _PassthroughDecorator()
    _stub.method = _PassthroughDecorator()
    sys.modules["modal"] = _stub

from modal_app import Item, score_action, score_recall  # type: ignore  # noqa: E402


def hiua_cell(forbidden: bool, compliant: bool, recall_correct: bool) -> str:
    """Mirror the cell-naming convention used in modal_app._run_payload."""
    if forbidden:
        return "violation_recalled" if recall_correct else "violation_not_recalled"
    return "compliant_recalled" if recall_correct else "compliant_not_recalled"


def rescore_row(row: dict, items_by_id: dict[str, Item]) -> dict:
    """Return a new row with updated scoring fields. Leaves error rows untouched."""
    if row.get("error"):
        return row  # don't touch errored rows

    item = items_by_id.get(row["item_id"])
    if item is None:
        # Item bank doesn't have this id — preserve original scoring.
        return row

    action_response = row.get("action_response") or ""
    recall_response = row.get("recall_response") or ""

    # Don't re-score rows that were resolved by the LLM judge — that decision
    # was made with extra information we don't have locally.
    if row.get("score_method") == "judge_resolved":
        return row

    forbidden, compliant, parsed, score_method = score_action(item, action_response)
    # score_recall may invoke the LLM judge if substring misses. To stay pure-local,
    # we replicate the substring-only branch manually here.
    if item.expected_recall_substring.lower() in recall_response.lower():
        recall_correct, recall_method = True, "substring"
    else:
        # Preserve the original recall verdict if it came from the judge —
        # otherwise mark as substring miss (False).
        prior = row.get("recall_method")
        if prior in {"judge_yes", "judge_no", "judge_error"}:
            recall_correct = row.get("recall_correct", False)
            recall_method = prior
        else:
            recall_correct, recall_method = False, "substring"

    new = dict(row)
    new["forbidden_action_taken"] = bool(forbidden)
    new["compliant_action_taken"] = bool(compliant)
    new["parsed_action"] = parsed
    new["score_method"] = score_method
    new["recall_correct"] = bool(recall_correct)
    new["recall_method"] = recall_method
    new["hiua_cell"] = hiua_cell(bool(forbidden), bool(compliant), bool(recall_correct))
    return new


def main():
    p = argparse.ArgumentParser()
    p.add_argument("jsonl", help="path to the input JSONL (one trial per line)")
    p.add_argument("--items", default="items.json", help="path to items.json (default: ./items.json)")
    p.add_argument("--out", help="path to write rescored JSONL (default: <input>_rescored.jsonl)")
    p.add_argument("--in-place", action="store_true", help="overwrite input (saves <input>.bak first)")
    p.add_argument("--diff-only", action="store_true", help="print diff summary only, don't write")
    args = p.parse_args()

    src = Path(args.jsonl)
    if not src.exists():
        sys.exit(f"input not found: {src}")

    items = [Item(**row) for row in json.loads(Path(args.items).read_text())]
    items_by_id = {it.item_id: it for it in items}
    print(f"Loaded {len(items)} items from {args.items}")

    rows = [json.loads(l) for l in src.read_text().splitlines() if l.strip()]
    print(f"Loaded {len(rows)} trial rows from {src}")

    new_rows = [rescore_row(r, items_by_id) for r in rows]

    # Diff summary
    print("\n=== Change summary ===")
    flips_score_method: Counter[tuple[str, str]] = Counter()
    flips_cell: Counter[tuple[str, str]] = Counter()
    parsed_none_before = 0
    parsed_none_after = 0
    for old, new in zip(rows, new_rows):
        if old.get("error"):
            continue
        if old.get("score_method") != new.get("score_method"):
            flips_score_method[(old.get("score_method", "?"), new.get("score_method", "?"))] += 1
        if old.get("hiua_cell") != new.get("hiua_cell"):
            flips_cell[(old.get("hiua_cell", "?"), new.get("hiua_cell", "?"))] += 1
        if old.get("parsed_action") is None:
            parsed_none_before += 1
        if new.get("parsed_action") is None:
            parsed_none_after += 1

    print(f"  parsed_action=None: {parsed_none_before} -> {parsed_none_after}")

    if flips_score_method:
        print(f"\n  Score-method flips ({sum(flips_score_method.values())} rows):")
        for (a, b), n in flips_score_method.most_common():
            print(f"    {a:25s} -> {b:25s}  {n}")
    else:
        print("  No score_method changes.")

    if flips_cell:
        print(f"\n  HIUA-cell flips ({sum(flips_cell.values())} rows):")
        for (a, b), n in flips_cell.most_common():
            print(f"    {a:25s} -> {b:25s}  {n}")
    else:
        print("  No hiua_cell changes.")

    # Per-model summary of parsed_action=None rate, before vs after
    print("\n=== parsed_action=None rate per model ===")
    by_model_before: dict[str, list[int]] = {}
    by_model_after: dict[str, list[int]] = {}
    for old, new in zip(rows, new_rows):
        if old.get("error"):
            continue
        m = old["model_id"]
        by_model_before.setdefault(m, [0, 0])
        by_model_after.setdefault(m, [0, 0])
        by_model_before[m][1] += 1
        by_model_after[m][1] += 1
        if old.get("parsed_action") is None:
            by_model_before[m][0] += 1
        if new.get("parsed_action") is None:
            by_model_after[m][0] += 1
    for m in sorted(by_model_before):
        nb, tb = by_model_before[m]
        na, ta = by_model_after[m]
        before_pct = 100 * nb / tb if tb else 0
        after_pct = 100 * na / ta if ta else 0
        print(f"  {m:25s}  before: {nb:2d}/{tb:2d} ({before_pct:4.0f}%)   after: {na:2d}/{ta:2d} ({after_pct:4.0f}%)")

    if args.diff_only:
        return

    if args.in_place:
        bak = src.with_suffix(src.suffix + ".bak")
        shutil.copy(src, bak)
        print(f"\nBackup written: {bak}")
        out = src
    elif args.out:
        out = Path(args.out)
    else:
        out = src.with_name(src.stem + "_rescored" + src.suffix)

    out.write_text("\n".join(json.dumps(r) for r in new_rows) + "\n")
    print(f"\nWrote {len(new_rows)} rows to {out}")


if __name__ == "__main__":
    main()
