#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH=.

CATEGORY_DIR=~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/model_testing
PATIENT_IDS=(1 2)   # <— run only these

for id in "${PATIENT_IDS[@]}"; do
  patient_dir="$CATEGORY_DIR/Patient_${id}"
  [[ -d "$patient_dir" ]] || { echo "⚠️  $patient_dir not found"; continue; }

  echo "Re-processing $patient_dir …"
  patient_name=$(basename "$patient_dir")
  case_name="mm_${patient_name}"

  chart="$patient_dir/limited_chart.json"
  txpt="$patient_dir/transcript.json"
  [[ -f "$chart" && -f "$txpt" ]] || { echo "  missing files — skipping"; continue; }

  uv run python case_builder.py --case "$case_name" --delete || true
  uv run python case_builder.py --chart "$chart" --transcript "$txpt" --case "$case_name" --cycles 1
  uv run python case_builder.py --case "$case_name" --summarize

  summary="evaluations/cases/$case_name/summary_initial.json"
  if [[ -f "$summary" ]]; then
    cp "$summary" "$patient_dir/note.json"
    echo "  Copied summary → $patient_dir/note.json"
  fi
done
