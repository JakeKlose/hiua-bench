# HIUA Pilot — Modal Experiment (v2, layered run)

A runnable pilot of the **Hallucination-Induced Unauthorized Action** benchmark sketched in the project memo. Fans out (model × item × seed) trials on Modal, scores each, runs a 3-judge hallucination labeler post-hoc, and produces a G-Theory-style analysis with Phi and Ep² coefficients.

Designed to run in **six layered phases** with confirmation gates between each, totaling ~4 hours of wall time and ~$165 in API spend (Modal compute is essentially free for this workload).

## Files

| File | Purpose |
|------|---------|
| `modal_app.py` | Modal orchestrator: per-provider trial functions with concurrency caps, tiered seed allocation, cost estimator |
| `items.json` | 24 base items (3 sub-constructs × 2 salience × 4 domains) |
| `paraphrase.py` | GPT-4o paraphrase generator → `items_expanded.json` (96 items: 24 originals + 72 paraphrases) |
| `judge.py` | 3-judge hallucination-type labeler (GPT-4o, Sonnet 4.6, Llama 70B) with Cohen's kappa |
| `analyze.py` | Basic 2×2 analysis + (with `--g-study`) full 2×4×2 cells, variance decomposition, Phi/Ep² |
| `run_pipeline.sh` | Layered runner: chains all six phases with confirmation gates |
| `requirements.txt` | Local Python deps |

## Four pipelines, pick one

| Pipeline | Cost | Time | Models | What you get |
|----------|------|------|--------|--------------|
| **Free** (`run_pipeline_free.sh`) | **$0** | ~3-6 hours | 5 OSS via Groq free tier | Existence proof, methodologically weakest |
| **OSS-paid** (`run_pipeline_oss.sh`) | ~$40 | ~3 hours | 9 OSS via Together | Same as free but more models, fewer rate-limit constraints |
| **Hybrid (Recommended for paper)** (`run_paper_pipeline.sh`) | ~$140 | ~4-6 hours | 12 OSS, 10 self-hosted on Modal | **Reproducible** — direct HuggingFace weights, documented vLLM config, methods-section claim |
| **Mixed** (`run_pipeline.sh`) | ~$105 | ~4 hours | 9 incl. frontier (Opus, GPT-4o, Gemini) | Frontier comparison, no reproducibility claim |

**Recommendation: hybrid pipeline if you have ~$140 Modal credit + ~$25 Together credit.**

The hybrid pipeline is the right choice if your paper needs to make a defensible reproducibility claim. Self-hosting 10 dense + small-MoE models on Modal H100s (with vLLM, pinned versions, documented sampling params) means another researcher can reproduce your numbers by re-running with the same HuggingFace weights. The 2 giant MoE models (DeepSeek V3.1 and R1) are too expensive to self-host at pilot scale (~$45/hr for 8x H100 nodes), so they go through Together AI's reference serving — a documented exception that fits cleanly in the methods section.

**Recommendation: start with the free pipeline.** If results are interesting, escalate to OSS-paid (more models, more seeds) or Mixed (frontier comparison).

The free pipeline trades off:
- **Smaller panel** (5 models vs 9): Llama 3.1 8B, Llama 3.3 70B, Gemma 2 9B, Qwen3 32B, DeepSeek-R1-Distill 70B
- **Rate-limited** (~3-6 hours wall time, mostly waiting on Groq's 30 RPM ceiling)
- **Reduced seed counts** (`--max-seeds-cheap 4` instead of 8 to fit Groq's 1,000-RPD-per-model quota)

It still produces the full 2×4×2 analysis, Phi/Ep², HIUA vs KBV comparison — just with weaker statistical power than the paid runs.

## Setup — hybrid (paper-scale, ~$140)

```bash
# 1. Modal (assumes you already have credit on your account)
pip install modal
modal token new

# 2. All three secrets
modal secret create groq-api-key GROQ_API_KEY=gsk_...        # free signup at console.groq.com
modal secret create together-api-key TOGETHER_API_KEY=...    # signup at together.ai, ~$25 credit needed
modal secret create hf-token HF_TOKEN=hf_...                 # huggingface.co/settings/tokens (gated Llama models)

# 3. Local env vars for paraphrase + judge scripts
export GROQ_API_KEY=gsk_...
export TOGETHER_API_KEY=...
export HF_TOKEN=hf_...

# 4. Install
pip install -r requirements.txt

# 5. Make runner executable
chmod +x run_paper_pipeline.sh

# 6. Run end-to-end with confirmation gates
./run_paper_pipeline.sh
```

The runner walks through 8 phases:

| Phase | What | Time | Cost |
|-------|------|------|------|
| A | Pre-cache all model weights to Modal volume | 30-60 min | ~$2-5 (CPU bandwidth) |
| B | Smoke test one self-hosted model | 3-5 min | ~$1 |
| C | Hybrid smoke + dev (24 items × 10 models × 1 seed) | 15-20 min | ~$10-20 |
| D | Paraphrase generation via Groq | 3 min | $0 |
| E | Cost estimate (no spend) | instant | $0 |
| F | Full G-study (96 items × 12 models × tiered seeds) | 2-4 hours | $100-120 |
| G | 3-judge labeling via Groq free tier | 30-60 min | $0 |
| H | Analysis (2×4×2 cells, Phi/Ep², kappa) | instant | $0 |

**The reproducibility claim** the paper can make after this run: "All open-weights models in the panel were self-hosted on Modal H100 GPUs using vLLM v0.6.4 with bfloat16 precision and documented sampling parameters. Weights were pulled from the canonical HuggingFace repositories on [date]. The two giant MoE models (DeepSeek V3.1 and R1) were served via Together AI's reference deployment due to their 8×H100 minimum serving requirement; we used Together's default sampling parameters for these models."

## Setup — free tier (recommended first)

```bash
# 1. Modal
pip install modal
modal token new

# 2. Groq free signup: https://console.groq.com (no payment required)
modal secret create groq-api-key GROQ_API_KEY=gsk_...

# 3. Local Python (paraphrase.py, judge.py, analyze.py)
pip install -r requirements.txt
export GROQ_API_KEY=gsk_...

# 4. Make the runner executable
chmod +x run_pipeline_free.sh
```

One key, one secret, $0 in API spend. Quotas reset at midnight UTC; if you hit a daily cap on the larger models, finish remaining work the next day.

## Setup — OSS-only (paid, full panel)

```bash
modal secret create together-api-key TOGETHER_API_KEY=...
export TOGETHER_API_KEY=...
chmod +x run_pipeline_oss.sh
```

## Setup — mixed (after OSS works)

```bash
modal secret create anthropic-api-key ANTHROPIC_API_KEY=sk-ant-...
modal secret create openai-api-key OPENAI_API_KEY=sk-...
modal secret create google-api-key GOOGLE_API_KEY=AIza...
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
chmod +x run_pipeline.sh
```

## OSS-only six-phase pipeline (recommended first run)

Run everything end-to-end with confirmation gates:

```bash
./run_pipeline_oss.sh
```

The OSS panel: Qwen 2.5 7B, Llama 3 8B Lite, GPT-OSS 20B, Gemma 4 31B (cheap tier, 8 seeds), Llama 3.3 70B, DeepSeek V3.1, GPT-OSS 120B (mid tier, 5 seeds), DeepSeek R1, Qwen3 235B (opus tier, 3 seeds). Nine models across five organizations (Meta, Alibaba, OpenAI, Google, DeepSeek). All weights are open; only the inference provider (Together) is closed.

Phase-by-phase:

| Phase | Tool | Time | Cost |
|-------|------|------|------|
| A. Smoke | `modal run modal_app.py::smoke_oss` | ~5s | ~$0.001 |
| B. Dev | `modal run modal_app.py::dev_oss` | ~2 min | ~$0.50 |
| C. Paraphrase | `python paraphrase.py --n 3 --backend oss` | ~3 min | ~$0.30 |
| D-pre. Estimate | `modal run modal_app.py::estimate --registry oss --mode full` | instant | $0 |
| D. Full run | `modal run modal_app.py::full_oss --confirm yes` | ~2 hours | ~$20–30 |
| E. Judge | `python judge.py <jsonl> --oss` | ~30 min | ~$15–20 |
| F. Analyze | `python analyze.py <judged_jsonl> --g-study` | instant | $0 |
| **Total** | | **~3 hours** | **~$40** |

Same scientific outputs as the mixed pipeline (2×4×2 cell occupancy, HIUA vs KBV, Phi/Ep², inter-rater kappa) but all via open-weights models served on Together. Stronger reproducibility story for the paper, weaker frontier-model comparison.

## The mixed six-phase pipeline

Run everything end-to-end with confirmation gates:

```bash
./run_pipeline.sh
```

Or invoke phases individually (recommended your first time so you can spot-check between each):

### Phase A — Smoke (~10s, ~$0.02)

```bash
modal run modal_app.py::smoke
```

Single trial against Claude Sonnet. Confirms wiring, secret setup, item-loading. If this fails, fix that before doing anything else.

### Phase B — Dev run (~3 min, ~$2)

```bash
modal run modal_app.py::dev
modal volume get hiua-results results/<latest>.jsonl .
python analyze.py <latest>.jsonl
```

24 items × 5 cheap/mid models × 1 seed = 120 trials. Skips Opus to save spend. Validates that the analysis pipeline produces sensible cell-occupancy numbers before you commit to the full run. **Inspect the output before continuing** — if the violation rate is 0% across the board, something is mis-configured (regex too strict, prompt template broken, etc.).

### Phase C — Paraphrase generation (~2 min, ~$3)

```bash
python paraphrase.py --n 3 --out items_expanded.json
```

GPT-4o produces 3 paraphrases per item, preserving sub-construct / domain / salience / trigger semantics while varying surface wording. Output is 96 items (24 originals + 72 paraphrases). **Spot-check 3 random paraphrases** in the output to make sure semantics held:

```bash
jq '.[24:28]' items_expanded.json
```

### Phase D-pre — Cost estimate (instant, $0)

```bash
modal run modal_app.py::estimate --items-path items_expanded.json --mode full
```

Prints a per-model spend projection for the full run. Tiered seed allocation: cheap models 8 seeds, mid 5, Opus 3. Estimate assumes ~800 input + ~600 output tokens per call — actuals can vary ±30%.

Expected output:
```
  model                     tier   seeds   trials    calls       cost
  gpt-4o-mini               cheap      8      768     1536      $0.85
  gemini-2.0-flash          cheap      8      768     1536      $0.36
  llama-3.1-70b             cheap      8      768     1536      $2.39
  qwen-2.5-72b              cheap      8      768     1536      $3.26
  gpt-4o                    mid        5      480      960      $7.68
  claude-sonnet-4.6         mid        5      480      960     $11.04
  claude-opus-4.6           opus       3      288      576     $32.99
  TOTAL                                                       ~$58.57
```

(Plus ~$3 paraphrase + ~$40 judge ≈ $100 total.)

### Phase D — Full G-study run (~3 hours, ~$60)

```bash
modal run modal_app.py::full --confirm yes
```

~3,500 trials across 7 models with tiered seeds. Per-provider concurrency caps (Anthropic=4, OpenAI=20, Google=8, Together=12) keep us under rate limits — adjust upward in `modal_app.py` if you're on higher API tiers. Modal will spawn as many containers as needed under these caps; compute cost is negligible.

Throughput: roughly 1–2 trials/second sustained, ~3 hours wall time. Logs every 50 trials. If a provider hits a rate limit, Modal's built-in `retries=2` handles transient failures; persistent failures appear in the output JSONL with an `error` field.

Pull the result:
```bash
modal volume ls hiua-results results/ | tail -3
modal volume get hiua-results results/<run_xxx_full.jsonl> .
```

### Phase E — Judge pass (~45 min, ~$40)

```bash
python judge.py run_xxx_full.jsonl
```

For each trial, three judges (GPT-4o, Claude Sonnet 4.6, Llama 70B) independently read the agent's chain-of-thought and label the hallucination type as `none`, `authorization`, `state`, or `tool`. Output: `run_xxx_full_judged.jsonl` with `judge_labels`, `judge_majority`, `judge_agreement` fields added per trial.

Inter-rater reliability reported at the end:
- Cohen's kappa for each pair of judges
- Mean pairwise kappa
- Three-way agreement rate

If mean kappa < 0.4 the construct's substantive validity is in trouble — the judges aren't agreeing on what counts as a hallucination, which means the labels aren't measuring a stable property. If kappa > 0.6 you have a defensible labeling regime for the paper.

### Phase F — Analysis (instant, $0)

```bash
python analyze.py run_xxx_full_judged.jsonl --g-study
```

Prints:

1. **Basic 2×2 cell occupancy** — `{forbidden?} × {recalled?}`. The HIUA-candidate and KBV cells are flagged.
2. **Per-model rates** — violation rate, recall rate, HIUA-candidate, KBV. The KBV column is your direct DriftBench comparison.
3. **Per-sub-construct rates** — which trigger type (authorization / state / tool) elicits the most violations.
4. **Salience effect** — does burying the prohibition mid-prompt increase violations?
5. **Item difficulty** — top-K hardest items (paraphrases rolled up with parents).
6. **Full 2×4×2 cell structure** — `{violation} × {hallu-type from judge} × {recall}`. This is the paper's target structure.
7. **HIUA conditional rate** — `P(violation | hallu-type ∈ {auth/state/tool} ∧ recall=True)`. The paper's headline number.
8. **HIUA vs. KBV ratio** — direct comparison of hallucination-induced vs. lucid violations.
9. **Per-judge label distribution** — for sanity-checking the judges aren't all collapsing to "none."
10. **G-study variance decomposition** — `σ²(person)`, `σ²(item)`, `σ²(residual)`, Generalizability coefficient (Ep²) and Dependability coefficient (Φ). D-study showing items-per-person needed for Φ ≥ 0.80.

**Important caveat about the G-study:** the implementation in `analyze.py` uses an approximate Henderson method-of-moments decomposition. For a publishable empirical pilot, re-run the variance decomposition through R's `gtheory` package (or an equivalent fully-crossed Python implementation) to get standard errors on the variance components. The Python output is correct in expectation but does not provide the SEs you'd want in a methods section.

## Cost summary

| Phase | Time | Cost |
|-------|------|------|
| A. Smoke | ~10s | ~$0.02 |
| B. Dev | ~3 min | ~$2 |
| C. Paraphrase | ~2 min | ~$3 |
| D. Full G-study | ~3 hours | ~$60 |
| E. Judge | ~45 min | ~$40 |
| F. Analysis | instant | $0 |
| **Total** | **~4 hours** | **~$105** |

Comfortably under the $200 ceiling. The remaining $95 of headroom is your safety margin for retries, additional paraphrase passes, or scaling up `n_seeds` if the first G-study run shows σ²(person) too small to be interpretable.

## Tuning knobs if the first full run shows problems

| Symptom | Knob |
|---------|------|
| σ²(item) > σ²(person) — benchmark measures item difficulty more than model differences | Generate more paraphrases (raise `--n` in `paraphrase.py`) to reduce item-specific noise |
| Phi < 0.80 — reliability insufficient | Raise tier seed counts in `TIER_SEEDS` (e.g., cheap=12, mid=8) and rerun the full pass |
| Mean kappa < 0.4 — judges disagree | Refine the `JUDGE_SYSTEM` prompt in `judge.py` with clearer category definitions and worked examples |
| Rate-limit retries during full run | Lower `PROVIDER_MAX_CONCURRENCY` in `modal_app.py`; for low-tier Anthropic accounts, set anthropic=2 |
| HIUA cell near empty | The trigger items aren't eliciting hallucinations on the models tested. Strengthen the triggers — make the forged emails / ambiguous identifiers / tool-docstring mismatches more enticing without crossing into jailbreak territory |

## What to do with the results in the paper

The pilot's contributions, in order of paper-load-bearingness:

1. **The 2×4×2 partition.** This is the move the paper claims existing benchmarks fail to make. Your pilot literally makes it. Report the table.
2. **The HIUA vs. KBV per-model comparison.** Pre-registered prediction in the paper: HIUA and KBV should be different rates with different cross-model orderings. Report whether they are.
3. **Inter-rater kappa for the hallucination labels.** The substantive-validity argument depends on this being defensible.
4. **Phi/Ep² variance decomposition.** The structural-validity argument depends on σ²(person) > σ²(item). If it isn't, that's also a publishable finding — it would mean the benchmark needs more items, not more models.
5. **Cross-domain transfer.** Spearman rank correlation across the four domains in per-model rates. Pre-registered prediction: positive but not unit. Report whichever way it goes.

If the pilot results contradict the paper's framing, **update the paper, don't bury the result.** The validity argument is the contribution; the empirical finding is supporting evidence either way. A negative result here ("KBV dominates HIUA 10:1, the hallucination-induced framing isn't the dominant mechanism") is itself a meaningful finding for the field.

## Known limitations (carried over from v1)

- Regex-based action scoring will mis-classify paraphrased compliance. Spot-check ~5% of trials manually.
- Substring-based recall scoring penalizes paraphrased recalls. Could be upgraded to an LLM-judge in a v3.
- No AI2-THOR embodied items. Digital-only for now. Embodied items are architecturally awkward on Modal and were deferred to v2.
- The Python G-study is approximate. For a real paper, use R's `gtheory` or an equivalent fully-crossed-design implementation for proper standard errors.
- Anthropic Tier 1-2 accounts will see longer wall times during the full run; the concurrency cap of 4 is conservative — raise it if you're on Tier 3+.
