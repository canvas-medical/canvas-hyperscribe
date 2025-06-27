#!/bin/bash
set -e
export PYTHONPATH=.
CATEGORY_DIR="~/canvas-hyperscribe/evaluations/cases/synthetic_unit_cases/med_management_v2"
CATEGORY_DIR=$(eval echo $CATEGORY_DIR)

echo "Generating profiles..."
uv run python evaluations/cases/synthetic_unit_cases/med_management_v2/profile_generator_v2.py
echo "Generating transcripts..."
uv run python evaluations/cases/synthetic_unit_cases/med_management_v2/transcript_generator.py
echo "Generating charts..."
uv run python evaluations/cases/synthetic_unit_cases/med_management_v2/chart_generator.py

for patient_dir in $(ls -d "$CATEGORY_DIR"/Patient_* | sort -t '_' -k2 -n); do
    echo "Processing $patient_dir..."
    patient_name=$(basename "$patient_dir")
    case_name="mm_${patient_name}"

    echo "Deleting previous case files for $case_name..."
    uv run python case_builder.py --case "$case_name" --delete

    uv run python case_builder.py \
        --chart "$patient_dir/limited_chart.json" \
        --transcript "$patient_dir/transcript.json" \
        --case "$case_name" \
        --cycles 1

    uv run python case_builder.py \
        --case "$case_name" \
        --summarize

    summary_path="evaluations/cases/$case_name/summary_initial.json"
    target_path="$patient_dir/note.json"
    if [[ -f "$summary_path" ]]; then
        cp "$summary_path" "$target_path"
        echo "Copied summary to $target_path"
    else
        echo "Summary not found for $case_name, skipping grading."
        continue
    fi

    uv run python evaluations/cases/synthetic_unit_cases/rubric.py \
        "$patient_dir/transcript.json" \
        "$patient_dir/limited_chart.json" \
        evaluations/cases/synthetic_unit_cases/canvas_context.json \
        "$patient_dir/rubric.json"

    PYTHONPATH=. uv run python evaluations/cases/synthetic_unit_cases/grader.py \
        "$patient_dir/rubric.json" \
        "$patient_dir/note.json" \
        "$patient_dir/scores.json"

    echo "Generation and evaluation complete for $patient_dir."
    done

echo "Generation and evaluation complete."



