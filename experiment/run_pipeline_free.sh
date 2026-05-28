#!/usr/bin/env bash
# FREE HIUA pilot — uses Groq's free tier for ALL inference. $0 in API spend.
# Trade-off: rate-limit-bound (~3-6 hours wall time) and smaller model panel.
#
# REQUIRED:
#   - GROQ_API_KEY (free signup at console.groq.com, $0 cost)
#   - Modal account + modal-cli installed
#
# Groq free-tier quotas (per model, per day, resets midnight UTC):
#   llama-3.1-8b-instant:       14,400 RPD  (the workhorse — used most)
#   llama-3.3-70b-versatile:     1,000 RPD
#   gemma2-9b-it:                1,000 RPD
#   qwen/qwen3-32b:              1,000 RPD
#   deepseek-r1-distill-llama-70b: 1,000 RPD
#
# Each trial costs 2 calls (action + recall). Default config below uses
# --max-seeds-cheap 4 (instead of 8) to keep all models within their daily caps.
# If you want full 8 seeds on the cheap tier, split the run across two days.
#
# Phases:
#   A. Smoke (~3s, $0)
#   B. Dev (~5 min, $0)
#   C. Paraphrase via Groq Llama-70B (~2 min, $0)
#   D. Cost estimate (informational; will show $0 against MODELS_GROQ pricing)
#   E. Full run with reduced seeds (~2-4 hours, $0)
#   F. Groq 3-judge labeling (~30-60 min, $0)
#   G. Analysis
#
# Usage:
#   ./run_pipeline_free.sh         # interactive
#   ./run_pipeline_free.sh --auto  # skip confirmation gates

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

if [[ -z "${GROQ_API_KEY:-}" ]]; then
  echo "ERROR: GROQ_API_KEY must be set in local shell"
  echo "  Sign up free at https://console.groq.com — no payment required"
  echo "  export GROQ_API_KEY=..."
  exit 1
fi

# ------------------------------------------------------------------
banner "PHASE A: Smoke (Groq Llama 3.1 8B, ~3s, \$0)"
# ------------------------------------------------------------------
confirm "Run smoke test?"
modal run modal_app.py::smoke_groq

# ------------------------------------------------------------------
banner "PHASE B: Groq dev run (cheap+mid, 1 seed, ~5 min, \$0)"
# ------------------------------------------------------------------
confirm "Run dev pass?"
modal run modal_app.py::dev_groq

echo
echo "Pull the dev-run JSONL to inspect:"
echo "  modal volume ls hiua-results results/ | tail -3"
echo "  modal volume get hiua-results results/<latest-dev_groq>.jsonl ."
echo "  python analyze.py <latest>.jsonl"
confirm "Continue to paraphrase generation?"

# ------------------------------------------------------------------
banner "PHASE C: Paraphrase via Groq Llama 3.3 70B (~2 min, \$0)"
# ------------------------------------------------------------------
confirm "Generate 3 paraphrases per item?"
python paraphrase.py --n 3 --backend groq --out items_expanded.json

confirm "Continue to full run?"

# ------------------------------------------------------------------
banner "PHASE D: Cost estimate (Groq free tier == \$0)"
# ------------------------------------------------------------------
modal run modal_app.py::estimate --items-path items_expanded.json --mode full --registry groq

confirm "Proceed to full free-tier run?"

# ------------------------------------------------------------------
banner "PHASE E: Full Groq run with reduced seeds (~2-4 hours, \$0)"
# ------------------------------------------------------------------
echo "Running with --max-seeds-cheap 4 to stay under per-model 1000 RPD caps."
echo "Per-model call counts (action + recall per trial):"
echo "  4 cheap models x 96 items x 4 seeds x 2 = 3072/4 = ~768 calls/model"
echo "  1 mid model    x 96 items x 5 seeds x 2 = ~960 calls"
echo "All within daily caps."
confirm "Launch?"
modal run modal_app.py::full_groq --confirm yes --max-seeds-cheap 4

echo
echo "Pull full-run JSONL:"
echo "  modal volume ls hiua-results results/ | tail -3"
echo "  modal volume get hiua-results results/<latest-full_groq>.jsonl ."
read -p "Path to local full-run JSONL: " FULL_LOCAL
[[ -f "$FULL_LOCAL" ]] || { echo "File not found: $FULL_LOCAL"; exit 1; }

# ------------------------------------------------------------------
banner "PHASE F: Groq 3-judge labeling (~30-60 min, \$0)"
# ------------------------------------------------------------------
echo "Judges: Llama 3.1 8B (14400 RPD), Llama 3.3 70B (1000 RPD), Gemma 2 9B (1000 RPD)"
echo "Using --workers 2 to slow down — keeps us under the 1000 RPD caps for the larger judges."
confirm "Launch Groq judge pass?"
python judge.py "$FULL_LOCAL" --groq --workers 2

JUDGED="${FULL_LOCAL%.jsonl}_judged.jsonl"

# ------------------------------------------------------------------
banner "PHASE G: Analysis (2x4x2 + G-study)"
# ------------------------------------------------------------------
python analyze.py "$JUDGED" --g-study

echo
echo "================================================================"
echo " DONE. Total API spend: \$0."
echo "================================================================"
echo "Files:"
echo "  $FULL_LOCAL     raw trials"
echo "  $JUDGED         judge-labeled trials"
echo "  items_expanded.json   item bank used"
echo
echo "If a judge or trial phase hit RPD caps and dropped trials, re-run"
echo "the missing portion the next UTC day — Groq quotas reset at midnight UTC."
