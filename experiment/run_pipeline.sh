#!/usr/bin/env bash
# Layered HIUA pilot runner — chains smoke -> dev -> paraphrase -> estimate -> full -> judge -> analyze.
# Each phase pauses for confirmation so you can review intermediate output before continuing.
#
# Prereqs:
#   - Modal CLI installed and authenticated (modal token new)
#   - Four Modal secrets created (anthropic-api-key, openai-api-key, google-api-key, together-api-key)
#   - OPENAI_API_KEY, ANTHROPIC_API_KEY, TOGETHER_API_KEY set in local shell (for paraphrase.py + judge.py)
#   - pip install -r requirements.txt
#
# Usage:
#   ./run_pipeline.sh              # interactive, walks through all phases
#   ./run_pipeline.sh --auto       # skip confirmation gates (NOT recommended for first run)

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

# ------------------------------------------------------------------
banner "PHASE A: Smoke test (1 trial, ~10s, ~\$0.02)"
# ------------------------------------------------------------------
confirm "Run smoke test?"
modal run modal_app.py::smoke

# ------------------------------------------------------------------
banner "PHASE B: Dev run (cheap+mid tier, 1 seed, ~3 min, ~\$2)"
# ------------------------------------------------------------------
confirm "Run dev pass on items.json?"
modal run modal_app.py::dev

echo
echo "Pull the dev-run JSONL locally to inspect before paraphrasing:"
echo "  modal volume ls hiua-results results/ | tail -5"
echo "  modal volume get hiua-results results/<latest-dev>.jsonl ."
echo "  python analyze.py <latest-dev>.jsonl"
confirm "Continue to paraphrase generation?"

# ------------------------------------------------------------------
banner "PHASE C: Paraphrase generation (~2 min, ~\$3)"
# ------------------------------------------------------------------
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "ERROR: OPENAI_API_KEY must be set in local shell for paraphrase.py"
  exit 1
fi
confirm "Generate 3 paraphrases per item via GPT-4o?"
python paraphrase.py --n 3 --out items_expanded.json

echo
echo "Spot-check the paraphrases before the full run:"
echo "  jq '.[24:28]' items_expanded.json    # first few generated paraphrases"
confirm "Continue to cost estimate?"

# ------------------------------------------------------------------
banner "PHASE D-pre: Cost estimate for full G-study run"
# ------------------------------------------------------------------
modal run modal_app.py::estimate --items-path items_expanded.json --mode full

confirm "Cost looks acceptable? Proceed to full run?"

# ------------------------------------------------------------------
banner "PHASE D: Full G-study run (~3 hours, ~\$120)"
# ------------------------------------------------------------------
echo "This will run ~15K trials across all 7 models with tiered seed allocation."
echo "  cheap models: 8 seeds   mid: 5 seeds   opus: 3 seeds"
echo "  per-provider concurrency caps applied to avoid rate-limit cascades"
confirm "Launch full run?"
modal run modal_app.py::full --confirm yes

echo
echo "Pull the full-run JSONL locally:"
echo "  modal volume ls hiua-results results/ | tail -5"
echo "  modal volume get hiua-results results/<latest-full>.jsonl ."
read -p "Path to local full-run JSONL: " FULL_LOCAL
[[ -f "$FULL_LOCAL" ]] || { echo "File not found: $FULL_LOCAL"; exit 1; }

# ------------------------------------------------------------------
banner "PHASE E: Judge pass (3 judges per trial, ~45 min, ~\$40)"
# ------------------------------------------------------------------
if [[ -z "${ANTHROPIC_API_KEY:-}" || -z "${TOGETHER_API_KEY:-}" ]]; then
  echo "ERROR: ANTHROPIC_API_KEY and TOGETHER_API_KEY must be set for judge.py"
  exit 1
fi
confirm "Launch 3-judge hallucination-type labeling on $FULL_LOCAL?"
python judge.py "$FULL_LOCAL"

JUDGED="${FULL_LOCAL%.jsonl}_judged.jsonl"

# ------------------------------------------------------------------
banner "PHASE F: Full analysis (2x4x2 cells + G-study)"
# ------------------------------------------------------------------
python analyze.py "$JUDGED" --g-study

echo
echo "Done. Headline files:"
echo "  $FULL_LOCAL    raw trials"
echo "  $JUDGED        with judge labels"
echo "  items_expanded.json   item bank used"
echo
echo "Report into the paper:"
echo "  1. The 2x4x2 cell occupancy table"
echo "  2. The HIUA vs KBV per-model comparison"
echo "  3. The variance components and Phi/Ep^2"
echo "  4. Inter-rater kappa (printed during judge.py)"
