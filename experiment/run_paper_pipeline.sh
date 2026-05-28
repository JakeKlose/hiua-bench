#!/usr/bin/env bash
# PAPER-SCALE HIUA pilot — hybrid pipeline using Modal GPU credit + Together API.
#
# 12-model panel (10 self-hosted on Modal GPUs, 2 via Together for the giant MoEs).
# Full G-study with paraphrases, 3-judge hallucination labeling, Phi/Ep^2.
# Estimated: 4-6 hours wall time, ~$140 total cost.
#
# REQUIRED:
#   - GROQ_API_KEY (free signup)
#   - TOGETHER_API_KEY (~$25 needed for the V3.1/R1 portion)
#   - HF_TOKEN (HuggingFace token, even for non-gated models)
#   - Modal account with ~$140+ in credits
#
# Run in order. Phases A-C are setup (~1 hour). D-G is the actual experiment.
#
# Usage:
#   ./run_paper_pipeline.sh                 # interactive, confirms each phase
#   ./run_paper_pipeline.sh --auto          # skip confirmation gates

set -euo pipefail

AUTO=0
if [[ "${1:-}" == "--auto" ]]; then AUTO=1; fi
cd "$(dirname "$0")"

confirm() {
  if [[ "$AUTO" -eq 1 ]]; then return 0; fi
  read -p "$1 [y/N] " ans
  [[ "$ans" =~ ^[Yy]$ ]] || { echo "Stopping."; exit 0; }
}

banner() {
  echo
  echo "================================================================"
  echo " $1"
  echo "================================================================"
}

# --- Secret checks ---------------------------------------------------------
[[ -n "${GROQ_API_KEY:-}" ]] || { echo "ERROR: GROQ_API_KEY not set"; exit 1; }
[[ -n "${TOGETHER_API_KEY:-}" ]] || { echo "ERROR: TOGETHER_API_KEY not set"; exit 1; }
[[ -n "${HF_TOKEN:-}" ]] || { echo "WARNING: HF_TOKEN not set — gated models (Llama) may fail to download"; }

# ------------------------------------------------------------------
banner "PHASE A: Weight pre-cache (~30-60 min, ~\$2-5 download cost)"
# ------------------------------------------------------------------
echo "Pulls ~200GB of HF weights to the hiua-llm-weights Modal volume."
echo "One-time cost; weights persist across runs."
confirm "Download all weights?"
modal run --detach selfhost.py::download_all_weights
echo "Track progress at the Modal dashboard URL above. Wait until all models show 'OK'."
confirm "Weights downloaded successfully?"

# ------------------------------------------------------------------
banner "PHASE B: Self-host smoke test (~3-5 min, ~\$1)"
# ------------------------------------------------------------------
echo "Tests Llama 3.3 70B loads and serves correctly on a single H100."
confirm "Run selfhost smoke?"
modal run selfhost.py::smoke_test --model llama-3.3-70b

# ------------------------------------------------------------------
banner "PHASE C: Hybrid smoke + dev (~15-20 min, ~\$10-20)"
# ------------------------------------------------------------------
echo "First, one-model smoke through the orchestrator (warms one H100 container):"
confirm "Run hybrid smoke?"
modal run modal_app.py::smoke_hybrid

echo
echo "Then dev pass: 24 items x 10 models x 1 seed = 240 trials."
echo "First run loads each model's weights (~2-3 min cold start each)."
confirm "Run dev_hybrid?"
modal run --detach modal_app.py::dev_hybrid

echo
echo "Pull dev results and inspect:"
echo "  modal volume ls hiua-results results/ | tail -3"
echo "  modal volume get hiua-results results/<latest-dev_hybrid>.jsonl ."
echo "  python analyze.py <latest>.jsonl"
confirm "Dev results look reasonable? Continue to paraphrase?"

# ------------------------------------------------------------------
banner "PHASE D: Paraphrase generation (~3 min, ~\$0.30)"
# ------------------------------------------------------------------
confirm "Generate 3 paraphrases per item via Groq Llama 3.3 70B?"
python paraphrase.py --n 3 --backend groq --out items_expanded.json
confirm "Paraphrases look good? Continue?"

# ------------------------------------------------------------------
banner "PHASE E: Cost estimate for full run"
# ------------------------------------------------------------------
modal run modal_app.py::estimate --items-path items_expanded.json --mode full --registry hybrid
echo
echo "Note: Modal GPU costs are not reflected in the estimate (they're per-hour, not per-token)."
echo "Budget ~\$80-120 in Modal GPU-hours + ~\$15-25 in Together for the MoE models."
confirm "Proceed to full run?"

# ------------------------------------------------------------------
banner "PHASE F: Full hybrid G-study (~2-4 hours, ~\$120-140)"
# ------------------------------------------------------------------
echo "96 items (24 base + 72 paraphrases) x 12 models x tiered seeds"
echo "Self-hosted models keep containers warm; Together MoE calls run in parallel."
confirm "Launch full hybrid run?"
modal run --detach modal_app.py::full_hybrid --confirm yes

echo
echo "Track at the Modal dashboard URL. When done:"
echo "  modal volume ls hiua-results results/ | tail -3"
echo "  modal volume get hiua-results results/<latest-full_hybrid>.jsonl ."
read -p "Path to local full-run JSONL: " FULL_LOCAL
[[ -f "$FULL_LOCAL" ]] || { echo "File not found: $FULL_LOCAL"; exit 1; }

# ------------------------------------------------------------------
banner "PHASE G: 3-judge hallucination labeling via Groq free tier (~30-60 min, \$0)"
# ------------------------------------------------------------------
confirm "Launch Groq judge pass on $FULL_LOCAL?"
python judge.py "$FULL_LOCAL" --groq --workers 2
JUDGED="${FULL_LOCAL%.jsonl}_judged.jsonl"

# ------------------------------------------------------------------
banner "PHASE H: Analysis"
# ------------------------------------------------------------------
python analyze.py "$JUDGED" --g-study

echo
echo "================================================================"
echo " DONE."
echo "================================================================"
echo "Headline files:"
echo "  $FULL_LOCAL    raw trials"
echo "  $JUDGED        judge-labeled"
echo "  items_expanded.json   item bank"
echo
echo "For the paper:"
echo "  1. 2x4x2 cell occupancy table"
echo "  2. HIUA vs KBV comparison across 12 models"
echo "  3. Phi/Ep^2 with self-hosted reproducibility guarantee"
echo "  4. Inter-rater kappa from the 3-judge ensemble"
echo "  5. Within-family scaling pairs (Llama 8B vs 70B, Qwen 7B vs 72B)"
echo "  6. Cross-organization comparison (Meta / Alibaba / DeepSeek / OpenAI / Google)"
