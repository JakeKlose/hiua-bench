"""Build benchmark.json from grading + timing data."""
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).parent

def collect(condition: str):
    pass_rates = []
    durations = []
    tokens = []
    per_eval = []
    for eval_dir in sorted(ROOT.glob("eval-*")):
        if not eval_dir.is_dir():
            continue
        cond_dir = eval_dir / condition
        if not cond_dir.exists():
            continue
        grading = json.loads((cond_dir / "grading.json").read_text())
        timing = json.loads((cond_dir / "timing.json").read_text())
        meta = json.loads((eval_dir / "eval_metadata.json").read_text())
        pr = grading["pass_count"] / grading["total"] if grading["total"] else 0
        pass_rates.append(pr)
        durations.append(timing["total_duration_seconds"])
        tokens.append(timing["total_tokens"])
        per_eval.append({
            "eval_id": grading["eval_id"],
            "eval_name": meta["eval_name"],
            "pass_count": grading["pass_count"],
            "total": grading["total"],
            "pass_rate": pr,
            "duration_seconds": timing["total_duration_seconds"],
            "total_tokens": timing["total_tokens"],
            "expectations": grading["expectations"],
        })
    return {
        "condition": condition,
        "pass_rate_mean": statistics.mean(pass_rates),
        "pass_rate_stddev": statistics.stdev(pass_rates) if len(pass_rates) > 1 else 0,
        "duration_mean": statistics.mean(durations),
        "duration_stddev": statistics.stdev(durations) if len(durations) > 1 else 0,
        "tokens_mean": statistics.mean(tokens),
        "tokens_stddev": statistics.stdev(tokens) if len(tokens) > 1 else 0,
        "per_eval": per_eval,
        "n_evals": len(pass_rates),
    }

with_skill = collect("with_skill")
without_skill = collect("without_skill")

benchmark = {
    "skill_name": "modal-setup",
    "iteration": 1,
    "configurations": [with_skill, without_skill],
    "delta": {
        "pass_rate": with_skill["pass_rate_mean"] - without_skill["pass_rate_mean"],
        "duration": with_skill["duration_mean"] - without_skill["duration_mean"],
        "tokens": with_skill["tokens_mean"] - without_skill["tokens_mean"],
    },
}

(ROOT / "benchmark.json").write_text(json.dumps(benchmark, indent=2))

# Also write a markdown summary
md = []
md.append("# Benchmark — modal-setup iteration 1\n")
md.append(f"| Configuration | Pass rate | Duration (s) | Tokens |")
md.append(f"|---|---|---|---|")
for c in (with_skill, without_skill):
    md.append(f"| **{c['condition']}** | {c['pass_rate_mean']:.1%} ± {c['pass_rate_stddev']:.1%} | {c['duration_mean']:.0f} ± {c['duration_stddev']:.0f} | {c['tokens_mean']:.0f} ± {c['tokens_stddev']:.0f} |")
md.append("")
md.append(f"**Delta (with_skill − without_skill):** pass rate {benchmark['delta']['pass_rate']:+.1%}, duration {benchmark['delta']['duration']:+.0f}s, tokens {benchmark['delta']['tokens']:+.0f}")
md.append("")
md.append("## Per-eval breakdown\n")
md.append("| Eval | With skill | Without skill |")
md.append("|---|---|---|")
for ws, wos in zip(with_skill["per_eval"], without_skill["per_eval"]):
    md.append(f"| {ws['eval_name']} | {ws['pass_count']}/{ws['total']} ({ws['duration_seconds']:.0f}s) | {wos['pass_count']}/{wos['total']} ({wos['duration_seconds']:.0f}s) |")

(ROOT / "benchmark.md").write_text("\n".join(md))
print("Wrote benchmark.json and benchmark.md")
print("\n" + "\n".join(md))
