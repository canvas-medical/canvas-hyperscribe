#!/bin/bash
set -e
export PYTHONPATH=~/canvas-hyperscribe/
CATEGORY_DIR="~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/med_management_rubric_testing"
CATEGORY_DIR=$(eval echo $CATEGORY_DIR)

for patient_dir in $(ls -d "$CATEGORY_DIR"/Patient_* | sort -t '_' -k2 -n); do
    echo "Processing $patient_dir..."

    echo "  Running splitting rubric generation..."
    uv run python evaluations/cases/synthetic_unit_cases/rubric_splitting.py \
        "$patient_dir/transcript.json" \
        "$patient_dir/limited_chart.json" \
        evaluations/cases/synthetic_unit_cases/canvas_context.json \
        "$patient_dir/rubric_splitting.json"

    echo "  Running cot rubric generation..."
    uv run python evaluations/cases/synthetic_unit_cases/rubric_cot.py \
        "$patient_dir/transcript.json" \
        "$patient_dir/limited_chart.json" \
        evaluations/cases/synthetic_unit_cases/canvas_context.json \
        "$patient_dir/rubric_cot.json"

    echo "Rubric runner 2 complete for $patient_dir."
done
