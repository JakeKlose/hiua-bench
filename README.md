# HIUA-Bench: Hallucination-Induced Unauthorized Action

CS321M (AI Measurement Science) term-paper project — Stanford, Spring 2026.

This repo contains the design, code, and pilot data for a benchmark that measures **HIUA**: the conditional rate at which an LLM agent, having hallucinated, executes an explicitly forbidden action. The argument is that no existing agent-safety benchmark isolates this construct from adjacent failure modes (lucid violation, jailbreak compliance, over-refusal, policy-invisible violation), and that a partitioned design is required to license deployment claims in irreversible-action settings.

## Status

v2 pipeline complete; v3 expansion in scope. Most recent inter-chat state is captured in [PROGRESS_v2.md](PROGRESS_v2.md).

**Headline v2 empirical results (n=466 clean trials, 13-model panel):**

- Cell occupancy: 86.1% compliant-recalled, 13.5% violation-recalled (KBV), 0.4% compliant-not-recalled, **0% violation-not-recalled** (HIUA-strict cell empty, a noted validity caveat).
- HIUA (looser construct, with hallucination-label criterion): 85.3% on the n=34 violation-with-recall subset.
- KBV: 3.6% on the n=390 recall-only subset. Within-trial HIUA-to-KBV ratio: 23.8:1.
- Non-monotonic three-level salience effect: 3.9% high < 17.9% mid < 21.7% low.
- Cross-provider replication on 4 models: 2 of 4 show meaningful provider effects (Llama-3.3-70B at 2.5× and GPT-OSS-120B at 2× when self-hosted vs Groq-served).
- Judge ensemble (Sonnet × Llama-4-Scout, 2-judge after Llama-3.3-70B RPD failure): Cohen's κ=0.626 (substantial), 91.5% observed agreement.
- G-theory: Ep²=0.82, Φ=0.75 (both above the 0.70 floor).

Paper draft at [paper_drafts/v1/overleaf/paper_long_v2.tex](paper_drafts/v1/overleaf/paper_long_v2.tex).

## Layout

```
.
├── README.md                                    ← this file (start here)
├── PROGRESS_v2.md                               ← live state + v3 priorities (read this second)
├── HANDOFF_v2.md                                ← historical v1→v2 transition notes
├── hallucination_to_unauthorized_action_memo.md ← the original research memo
├── experiment/
│   ├── items.json                               ← original 24 items (high/low salience only)
│   ├── items_mid.json                           ← 12 mid-salience items added in v2
│   ├── items_36.json                            ← merged 36-item bank (use this for analysis)
│   ├── modal_app.py                             ← orchestrator, trial dispatch, scoring
│   ├── selfhost_serve.py                        ← vLLM-on-Modal per-model serving
│   ├── selfhost_v1_broken.py.archive            ← preserved-for-reference v1 selfhost
│   ├── judge.py                                 ← hallucination-type labeling (4 ensemble flags)
│   ├── analyze.py                               ← G-Theory analysis (basic 2x2 + --g-study)
│   ├── rescore.py                               ← pure-local re-scorer for parser updates
│   ├── paraphrase.py                            ← item paraphrase generator
│   ├── inspect_trials.py                        ← qualitative trial inspector
│   ├── run_20260528_combined_all.jsonl                       ← unified 468-trial pre-judge
│   ├── run_20260528_combined_all_judged_2judge.jsonl         ← ★ paper numbers source
│   └── run_*.jsonl                              ← other intermediate trial-data snapshots
├── paper_drafts/v1/overleaf/
│   ├── paper_long.tex                           ← original v1 draft
│   ├── paper_long_v2.tex                        ← v2 draft (current submission target)
│   ├── paper_workshop.tex                       ← workshop cut
│   ├── empirical_pilot_template.tex             ← slot-fill template for results section
│   ├── pilot_v2_FILLED.tex                      ← reference: filled-in v2 §5 + App. B
│   ├── main_v2.tex                              ← updated main.tex with integrated v2 sections
│   └── references.bib                           ← 40 verified citations
├── agents/                                      ← autonomous subagent specs used to draft v1
└── skills/                                      ← Anthropic Skills built for this project
    └── modal-setup-workspace/                   ← lessons from debugging Modal+vLLM
```

## Quick start (reproducing the Groq pilot)

```bash
cd experiment

# Prerequisites: Modal account, GROQ_API_KEY in your Modal workspace,
# huggingface_hub auth via `huggingface-cli login` (for the gated models).
pip install groq openai anthropic

# 1. Run dev_groq: 6 models × 24 items × 1 seed = 144 trials, ~$0, ~10 min.
modal run --detach modal_app.py::dev_groq

# 2. Pull the JSONL.
modal volume ls hiua-results results/ | head -3
modal volume get hiua-results results/run_<latest>.jsonl .

# 3. Re-score against the patched parser (handles gpt-oss Harmony format).
python3 rescore.py run_<...>.jsonl --out run_<...>_rescored.jsonl

# 4. Run the 3-judge hallucination-type labeling pass.
python3 judge.py run_<...>_rescored.jsonl --groq --items items.json --workers 2 \
    --out run_<...>_rescored_judged.jsonl

# 5. Full G-study analysis.
python3 analyze.py run_<...>_rescored_judged.jsonl --g-study
```

## Self-hosted vLLM panel (v3)

The selfhost path (`experiment/selfhost_serve.py` + `modal_app.py::dev_selfhost`) is the open-weights extension of the panel: Qwen-2.5-7B/72B, Llama-3.1-8B/3.3-70B, Gemma-2-27B, GPT-OSS-20B/120B, Qwen3-235B (MoE). Architecture: each model deployed as its own Modal `@modal.web_server` function exposing an OpenAI-compatible HTTPS endpoint; orchestrator calls them via the `openai` SDK with `base_url=` overrides.

See `PROGRESS_v2.md` for the deploy-and-smoke runbook. v1's failed selfhost attempt is archived as `selfhost_v1_broken.py.archive` for reference; do not import it.

## Construct definition

**HIUA = P(forbidden action | hallucination ∧ salient prohibition)**

Existing benchmarks (AgentHarm, ToolEmu, SafeAgentBench, RoboPAIR, DriftBench, others) measure adjacent constructs but confound HIUA with at least four other failure modes: lucid violation (knows-but-violates), jailbreak compliance, over-refusal, and policy-invisible violation. A benchmark that does not partition these mechanisms cannot license deployment claims in irreversible-action settings (lethal robotics, military targeting, autonomous trading).

The design factorially crosses:

- 3 hallucination sub-types (authorization, state, tool)
- 3 prohibition-salience levels (early-system, mid-system, tool-docstring)
- 4 domains (file operations, communication, financial, embodied)

yielding 36 base items. The v2 pilot uses the full 36-item bank across a 13-model panel (468 trials). Three scores per trial: outcome (regex + refusal-prefix + LLM-judge fallback), hallucination type (2-judge LLM ensemble after the third Groq-served judge hit a daily request cap), and recall probe (substring + judge fallback). The 2×4×2 cell structure partitions HIUA from KBV and from lucid compliance.

## Roadmap

The v2 pilot reported in `paper_long_v2.tex` establishes empirical realizability and provides preliminary G-theory reliability (Ep²=0.82, Φ=0.75). The following extensions are in scope for v3 work.

**Statistical power and reliability.**
- Multi-seed runs (≥3 seeds per item × model) to populate the occasion facet of the G-study; current single-seed design forecloses within-trial variance components.
- Paraphrase expansion (4 paraphrases per item via `paraphrase.py`) to test paraphrase-stability of per-item rates and surface item-construction effects.
- Full Generalizability-Theory analysis via R's `gtheory` package, replacing the approximate Henderson method-of-moments decomposition in `analyze.py`. The decomposition would add standard errors on variance components and proper D-study projections.

**Construct extensions.**
- Embodied items in AI2-THOR or HEAL-derived scenes to test the digital-to-embodied transfer claim that the consequential-aspect argument rests on.
- Harder recall probes (asking for specific filename patterns, deadlines, scope conditions) to populate the empty `violation-not-recalled` cell. The current item bank uses short prominent prohibitions that paraphrase-stable probes can recover at near-ceiling rates.
- Mid-salience item bank expansion. The 12 mid-salience items added in v2 (`items_mid.json`) are the minimum to support the three-level factorial. A larger bank with more lexical variation per cell would strengthen the salience-effect claim.

**Panel extensions.**
- Frontier closed models (GPT-4 class, Claude class, Gemini class) in the actor panel. The nomological-network predictions in §4.4 and Appendix D currently remain untested at frontier scale.
- Within-family scaling pairs (e.g., Qwen 2.5 family at 7B, 14B, 32B, 72B) to support capability-correlated predictions.
- Cross-provider replication on additional models. The v2 pilot covers Llama 3.1 8B, Llama 3.3 70B, GPT-OSS 20B, and GPT-OSS 120B served both via hosted endpoint and self-hosted vLLM. Extending this to more models would let us factor out provider effects more rigorously.

**Judge ensemble hardening.**
- Replace the Groq-free-tier Llama 3.3 70B Versatile judge with one that does not hit daily-request caps. Candidates: paid-tier Groq, Anthropic Claude Sonnet (used as one of two judges in v2), or a self-hosted vLLM Llama judge served via the same infrastructure as the actor panel.
- Human spot-check calibration on 10% of trials, recommended by the design plan in §4.3 but not run in v2. Inter-rater human-vs-ensemble agreement would let the substantive-validity argument rest on something stronger than two-judge LLM agreement.

**Reproducibility infrastructure.**
- Inspect Evals scaffolding wrapper for the items + scoring stack. The current `experiment/modal_app.py` orchestration is HIUA-specific; an Inspect Evals task definition would let other researchers reproduce or extend the pilot using their own model panel.
- Item bank versioning. The current `items.json` (24 items) and `items_mid.json` (12 items) are joined into `items_36.json` for analysis. A canonical versioned `items.json` with clear inclusion criteria would simplify external reproduction.

## Citation

Pending. Term paper draft in `paper_drafts/v1/overleaf/paper_long_v2.tex`.

## License

Code: MIT (pending). Items and trial data: CC-BY 4.0 (pending). Final license attached prior to public release.
