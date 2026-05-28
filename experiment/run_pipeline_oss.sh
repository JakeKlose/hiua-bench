#!/usr/bin/env bash
# OSS-only HIUA pilot runner — uses Together AI for ALL inference.
# Only requires TOGETHER_API_KEY (locally) and the together-api-key Modal secret.
#
# Phases:
#   A. Smoke (1 trial, ~5s, ~$0.001)
#   B. Dev (24 items x cheap+mid OSS models x 1 seed, ~2 min, ~$0.50)
#   C. Paraphrase via DeepSeek V3.1 (~3 min, ~$0.30)
#   D. Cost estimate
#   E. Full G-study run (~2 hours, ~$20-30)
#   F. OSS 3-judge labeling (~30 min, ~$15-20)
#   G. Analysis
#
# Total: ~3 hours wall time, ~$40 in Together credits.
#
# Usage:
#   ./run_pipeline_oss.sh         # interactive, walks through each phase
#   ./run_pipeline_oss.sh --auto  # skip confirmation gates

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

if [[ -z "${TOGETHER_API_KEY:-}" ]]; then
  echo "ERROR: TOGETHER_API_KEY must be set in local shell"
  echo "  export TOGETHER_API_KEY=..."
  exit 1
fi

# ------------------------------------------------------------------
banner "PHASE A: Smoke (Llama 3.3 70B via Together, ~5s, ~\$0.001)"
# ------------------------------------------------------------------
confirm "Run smoke test?"
modal run modal_app.py::smoke_oss

# ------------------------------------------------------------------
banner "PHASE B: OSS dev run (cheap+mid tier, 1 seed, ~2 min, ~\$0.50)"
# ------------------------------------------------------------------
confirm "Run dev pass on items.json?"
modal run modal_app.py::dev_oss

echo
echo "Pull dev-run JSONL to inspect:"
echo "  modal volume ls hiua-results results/ | tail -3"
echo "  modal volume get hiua-results results/<latest-dev_oss>.jsonl ."
echo "  python analyze.py <latest>.jsonl"
confirm "Continue to paraphrase generation?"

# ------------------------------------------------------------------
banner "PHASE C: Paraphrase generation via DeepSeek V3.1 (~3 min, ~\$0.30)"
# ------------------------------------------------------------------
confirm "Generate 3 paraphrases per item?"
python paraphrase.py --n 3 --backend oss --out items_expanded.json

echo
echo "Spot-check the paraphrases:"
echo "  jq '.[24:28]' items_expanded.json"
confirm "Continue to cost estimate?"

# ------------------------------------------------------------------
banner "PHASE D: Cost estimate for OSS full run"
# ------------------------------------------------------------------
modal run modal_app.py::estimate --items-path items_expanded.json --mode full --registry oss

confirm "Cost looks OK? Proceed to full OSS run?"

# ------------------------------------------------------------------
banner "PHASE E: Full OSS G-study (~2 hours, ~\$20-30)"
# ------------------------------------------------------------------
echo "9 OSS models with tiered seed allocation (cheap=8, mid=5, opus=3)."
confirm "Launch full OSS run?"
modal run modal_app.py::full_oss --confirm yes

echo
echo "Pull full-run JSONL:"
echo "  modal volume ls hiua-results results/ | tail -3"
echo "  modal volume get hiua-results results/<latest-full_oss>.jsonl ."
read -p "Path to local full-run JSONL: " FULL_LOCAL
[[ -f "$FULL_LOCAL" ]] || { echo "File not found: $FULL_LOCAL"; exit 1; }

# ------------------------------------------------------------------
banner "PHASE F: OSS 3-judge labeling (~30 min, ~\$15-20)"
# ------------------------------------------------------------------
echo "Judges: Llama 3.3 70B, DeepSeek V3.1, Qwen3 235B (all via Together)."
confirm "Launch OSS judge pass on $FULL_LOCAL?"
python judge.py "$FULL_LOCAL" --oss

JUDGED="${FULL_LOCAL%.jsonl}_judged.jsonl"

# ------------------------------------------------------------------
banner "PHASE G: Analysis (2x4x2 + G-study)"
# ------------------------------------------------------------------
python analyze.py "$JUDGED" --g-study

echo
echo "Done. OSS-only results in:"
echo "  $FULL_LOCAL     raw trials"
echo "  $JUDGED         with judge labels"
echo "  items_expanded.json   item bank used"
