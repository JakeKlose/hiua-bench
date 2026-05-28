# Benchmark — modal-setup iteration 1

| Configuration | Pass rate | Duration (s) | Tokens |
|---|---|---|---|
| **with_skill** | 100.0% ± 0.0% | 80 ± 63 | 29885 ± 8951 |
| **without_skill** | 72.5% ± 24.7% | 71 ± 23 | 21684 ± 1941 |

**Delta (with_skill − without_skill):** pass rate +27.5%, duration +9s, tokens +8200

## Per-eval breakdown

| Eval | With skill | Without skill |
|---|---|---|
| first-time-llama-host | 8/8 (172s) | 6/8 (100s) |
| debug-secret-not-found | 4/4 (38s) | 3/4 (45s) |
| vllm-dependency-conflict | 5/5 (44s) | 2/5 (68s) |
| long-run-killed-by-sleep | 5/5 (66s) | 5/5 (71s) |