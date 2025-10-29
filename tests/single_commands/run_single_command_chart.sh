#!/bin/bash

# Script to run case_builder for all single command transcripts

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Define paths relative to script directory
TRANSCRIPT_DIR="$SCRIPT_DIR/transcripts"
CHART_FILE="$SCRIPT_DIR/limited_caches/for_single_command.json"

# Change to project root (two levels up from script directory)
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "Project root: $PROJECT_ROOT"
echo "Using transcript directory: $TRANSCRIPT_DIR"
echo "Using chart file: $CHART_FILE"
echo ""

echo "run adjust_prescription..."
uv run python -m scripts.case_builder \
  --case adjust_prescription \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/adjust_prescription.json" \
  --chart "$CHART_FILE"

echo "run allergy..."
uv run python -m scripts.case_builder \
  --case allergy \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/allergy.json" \
  --chart "$CHART_FILE"

echo "run assess..."
uv run python -m scripts.case_builder \
  --case assess \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/assess.json" \
  --chart "$CHART_FILE"

echo "run close_goal..."
uv run python -m scripts.case_builder \
  --case close_goal \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/close_goal.json" \
  --chart "$CHART_FILE"

echo "run diagnose..."
uv run python -m scripts.case_builder \
  --case diagnose \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/diagnose.json" \
  --chart "$CHART_FILE"

echo "run family_history..."
uv run python -m scripts.case_builder \
  --case family_history \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/family_history.json" \
  --chart "$CHART_FILE"

echo "run follow_up..."
uv run python -m scripts.case_builder \
  --case follow_up \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/follow_up.json" \
  --chart "$CHART_FILE"

echo "run goal..."
uv run python -m scripts.case_builder \
  --case goal \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/goal.json" \
  --chart "$CHART_FILE"

echo "run history_of_present_illness..."
uv run python -m scripts.case_builder \
  --case history_of_present_illness \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/history_of_present_illness.json" \
  --chart "$CHART_FILE"

echo "run imaging_order..."
uv run python -m scripts.case_builder \
  --case imaging_order \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/imaging_order.json" \
  --chart "$CHART_FILE"

echo "run immunization_statement..."
uv run python -m scripts.case_builder \
  --case immunization_statement \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/immunization_statement.json" \
  --chart "$CHART_FILE"

echo "run immunize..."
uv run python -m scripts.case_builder \
  --case immunize \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/immunize.json" \
  --chart "$CHART_FILE"

echo "run instruct..."
uv run python -m scripts.case_builder \
  --case instruct \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/instruct.json" \
  --chart "$CHART_FILE"

echo "run lab_order..."
uv run python -m scripts.case_builder \
  --case lab_order \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/lab_order.json" \
  --chart "$CHART_FILE"

echo "run medical_history..."
uv run python -m scripts.case_builder \
  --case medical_history \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/medical_history.json" \
  --chart "$CHART_FILE"

echo "run medication..."
uv run python -m scripts.case_builder \
  --case medication \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/medication.json" \
  --chart "$CHART_FILE"

echo "run perform..."
uv run python -m scripts.case_builder \
  --case perform \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/perform.json" \
  --chart "$CHART_FILE"

echo "run plan..."
uv run python -m scripts.case_builder \
  --case plan \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/plan.json" \
  --chart "$CHART_FILE"

echo "run prescription..."
uv run python -m scripts.case_builder \
  --case prescription \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/prescription.json" \
  --chart "$CHART_FILE"

echo "run reason_for_visit..."
uv run python -m scripts.case_builder \
  --case reason_for_visit \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/reason_for_visit.json" \
  --chart "$CHART_FILE"

echo "run refer..."
uv run python -m scripts.case_builder \
  --case refer \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/refer.json" \
  --chart "$CHART_FILE"

echo "run refill..."
uv run python -m scripts.case_builder \
  --case refill \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/refill.json" \
  --chart "$CHART_FILE"

echo "run remove_allergy..."
uv run python -m scripts.case_builder \
  --case remove_allergy \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/remove_allergy.json" \
  --chart "$CHART_FILE"

echo "run resolve_condition..."
uv run python -m scripts.case_builder \
  --case resolve_condition \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/resolve_condition.json" \
  --chart "$CHART_FILE"

echo "run stop_medication..."
uv run python -m scripts.case_builder \
  --case stop_medication \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/stop_medication.json" \
  --chart "$CHART_FILE"

echo "run surgery_history..."
uv run python -m scripts.case_builder \
  --case surgery_history \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/surgery_history.json" \
  --chart "$CHART_FILE"

echo "run task..."
uv run python -m scripts.case_builder \
  --case task \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/task.json" \
  --chart "$CHART_FILE"

echo "run update_diagnose..."
uv run python -m scripts.case_builder \
  --case update_diagnose \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/update_diagnose.json" \
  --chart "$CHART_FILE"

echo "run update_goal..."
uv run python -m scripts.case_builder \
  --case update_goal \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/update_goal.json" \
  --chart "$CHART_FILE"

echo "run vitals..."
uv run python -m scripts.case_builder \
  --case vitals \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/vitals.json" \
  --chart "$CHART_FILE"

echo "All single command tests completed!"
