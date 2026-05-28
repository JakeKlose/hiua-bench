# HIUA-Bench: Hallucination-Induced Unauthorized Action

CS321M (AI Measurement Science) term-paper project — Stanford, Spring 2026.

This repo contains the design, code, and pilot data for a benchmark that measures **HIUA**: the conditional rate at which an LLM agent, having hallucinated, executes an explicitly forbidden action. The argument is that no existing agent-safety benchmark isolates this construct from adjacent failure modes (lucid violation, jailbreak compliance, over-refusal, policy-invisible violation), and that a partitioned design is required to license deployment claims in irreversible-action settings.

## Status

Work in progress. Most recent state is captured in [PROGRESS_v2.md](PROGRESS_v2.md). Headline empirical results from the Groq dev-tier pilot (n=142, 6 models): 0% HIUA-candidate, 10.6% KBV (lucid violation), 100% recall ceiling (a real validity caveat noted in the paper), 20× salience effect.

## Layout

```
.
├── README.md                                    ← this file
├── HANDOFF_v2.md                                ← v1 → v2 transition notes (read this first)
├── PROGRESS_v2.md                               ← live state, inter-chat coordination log
├── hallucination_to_unauthorized_action_memo.md ← the original research memo
├── experiment/
│   ├── items.json                               ← 24-item factorial benchmark
│   ├── modal_app.py                             ← orchestrator, trial dispatch, scoring
│   ├── selfhost_serve.py                        ← vLLM-on-Modal per-model serving (v3)
│   ├── selfhost_v1_broken.py.archive            ← preserved-for-reference v1 selfhost
│   ├── judge.py                                 ← 3-judge hallucination-type labeling
│   ├── analyze.py                               ← G-Theory analysis (basic 2x2 + --g-study)
│   ├── rescore.py                               ← pure-local re-scorer for parser updates
│   ├── paraphrase.py                            ← item paraphrase generator
│   ├── inspect_trials.py                        ← qualitative trial inspector
│   └── run_*.jsonl                              ← trial data (Groq pilot + partial selfhost)
├── paper_drafts/v1/overleaf/
│   ├── paper_long.tex                           ← CS321M term paper (em-dash style)
│   ├── paper_long_koyejo.tex                    ← submission version (Koyejo lab style)
│   ├── paper_workshop.tex                       ← workshop cut
│   ├── empirical_pilot_template.tex             ← slot-fill template for results section
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

yielding 36 base items. The pilot uses a 24-item subset. Three scores per trial: outcome (regex + refusal-prefix + LLM-judge fallback), hallucination type (3-judge LLM ensemble), and recall probe (substring + judge fallback). The 2×4×2 cell structure partitions HIUA from KBV and from lucid compliance.

## Citation

Pending. Term paper draft in `paper_drafts/v1/overleaf/paper_long_koyejo.tex`.

## License

Code: MIT (pending). Items and trial data: CC-BY 4.0 (pending). Final license attached prior to public release.
