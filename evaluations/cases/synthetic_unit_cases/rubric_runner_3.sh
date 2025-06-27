#!/bin/bash
set -e
export PYTHONPATH=~/canvas-hyperscribe/
CATEGORY_DIR="~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/med_management_rubric_testing"
CATEGORY_DIR=$(eval echo $CATEGORY_DIR)

for patient_dir in $(ls -d "$CATEGORY_DIR"/Patient_* | sort -t '_' -k2 -n); do
    echo "Processing $patient_dir..."

    echo "  Running replication rubric generation..."
    uv run python evaluations/cases/synthetic_unit_cases/rubric_replication.py \
        "$patient_dir/transcript.json" \
        "$patient_dir/limited_chart.json" \
        evaluations/cases/synthetic_unit_cases/canvas_context.json \
        "$patient_dir"

    echo "  Running prelabel rubric generation..."
    uv run python evaluations/cases/synthetic_unit_cases/rubric_prelabel.py \
        "$patient_dir/transcript.json" \
        "$patient_dir/limited_chart.json" \
        evaluations/cases/synthetic_unit_cases/canvas_context.json \
        "$patient_dir/transcript_labeled.json" \
        "$patient_dir/rubric_prelabel.json"

    echo "Replication and prelabel complete for $patient_dir."
done
