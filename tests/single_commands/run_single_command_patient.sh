#!/bin/bash

# Script to run case_builder for all single command transcripts

# Check if patient ID argument is provided
if [ -z "$1" ]; then
  echo "Error: Patient ID is required as first argument"
  echo "Usage: $0 <patient_id>"
  exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Define paths relative to script directory
TRANSCRIPT_DIR="$SCRIPT_DIR/transcripts"

# Change to project root (two levels up from script directory)
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

PATIENT_ID="$1"
echo "Project root: $PROJECT_ROOT"
echo "Running tests with patient ID: $PATIENT_ID"
echo "Using transcript directory: $TRANSCRIPT_DIR"
echo ""

echo "run adjust_prescription..."
uv run python -m scripts.case_builder \
  --case adjust_prescription \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/adjust_prescription.json" \
  --patient "$PATIENT_ID" --render

echo "run allergy..."
uv run python -m scripts.case_builder \
  --case allergy \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/allergy.json" \
  --patient "$PATIENT_ID" --render
exit

echo "run assess..."
uv run python -m scripts.case_builder \
  --case assess \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/assess.json" \
  --patient "$PATIENT_ID" --render

echo "run close_goal..."
uv run python -m scripts.case_builder \
  --case close_goal \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/close_goal.json" \
  --patient "$PATIENT_ID" --render

echo "run diagnose..."
uv run python -m scripts.case_builder \
  --case diagnose \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/diagnose.json" \
  --patient "$PATIENT_ID" --render

echo "run family_history..."
uv run python -m scripts.case_builder \
  --case family_history \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/family_history.json" \
  --patient "$PATIENT_ID" --render

echo "run follow_up..."
uv run python -m scripts.case_builder \
  --case follow_up \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/follow_up.json" \
  --patient "$PATIENT_ID" --render

echo "run goal..."
uv run python -m scripts.case_builder \
  --case goal \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/goal.json" \
  --patient "$PATIENT_ID" --render

echo "run history_of_present_illness..."
uv run python -m scripts.case_builder \
  --case history_of_present_illness \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/history_of_present_illness.json" \
  --patient "$PATIENT_ID" --render

echo "run imaging_order..."
uv run python -m scripts.case_builder \
  --case imaging_order \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/imaging_order.json" \
  --patient "$PATIENT_ID" --render

echo "run immunization_statement..."
uv run python -m scripts.case_builder \
  --case immunization_statement \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/immunization_statement.json" \
  --patient "$PATIENT_ID" --render

echo "run immunize..."
uv run python -m scripts.case_builder \
  --case immunize \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/immunize.json" \
  --patient "$PATIENT_ID" --render

echo "run instruct..."
uv run python -m scripts.case_builder \
  --case instruct \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/instruct.json" \
  --patient "$PATIENT_ID" --render

echo "run lab_order..."
uv run python -m scripts.case_builder \
  --case lab_order \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/lab_order.json" \
  --patient "$PATIENT_ID" --render

echo "run medical_history..."
uv run python -m scripts.case_builder \
  --case medical_history \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/medical_history.json" \
  --patient "$PATIENT_ID" --render

echo "run medication..."
uv run python -m scripts.case_builder \
  --case medication \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/medication.json" \
  --patient "$PATIENT_ID" --render

echo "run perform..."
uv run python -m scripts.case_builder \
  --case perform \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/perform.json" \
  --patient "$PATIENT_ID" --render

echo "run plan..."
uv run python -m scripts.case_builder \
  --case plan \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/plan.json" \
  --patient "$PATIENT_ID" --render

echo "run prescription..."
uv run python -m scripts.case_builder \
  --case prescription \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/prescription.json" \
  --patient "$PATIENT_ID" --render

echo "run reason_for_visit..."
uv run python -m scripts.case_builder \
  --case reason_for_visit \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/reason_for_visit.json" \
  --patient "$PATIENT_ID" --render

echo "run refer..."
uv run python -m scripts.case_builder \
  --case refer \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/refer.json" \
  --patient "$PATIENT_ID" --render

echo "run refill..."
uv run python -m scripts.case_builder \
  --case refill \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/refill.json" \
  --patient "$PATIENT_ID" --render

echo "run remove_allergy..."
uv run python -m scripts.case_builder \
  --case remove_allergy \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/remove_allergy.json" \
  --patient "$PATIENT_ID" --render

echo "run resolve_condition..."
uv run python -m scripts.case_builder \
  --case resolve_condition \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/resolve_condition.json" \
  --patient "$PATIENT_ID" --render

echo "run stop_medication..."
uv run python -m scripts.case_builder \
  --case stop_medication \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/stop_medication.json" \
  --patient "$PATIENT_ID" --render

echo "run surgery_history..."
uv run python -m scripts.case_builder \
  --case surgery_history \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/surgery_history.json" \
  --patient "$PATIENT_ID" --render

echo "run task..."
uv run python -m scripts.case_builder \
  --case task \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/task.json" \
  --patient "$PATIENT_ID" --render

echo "run update_diagnose..."
uv run python -m scripts.case_builder \
  --case update_diagnose \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/update_diagnose.json" \
  --patient "$PATIENT_ID" --render

echo "run update_goal..."
uv run python -m scripts.case_builder \
  --case update_goal \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/update_goal.json" \
  --patient "$PATIENT_ID" --render

echo "run vitals..."
uv run python -m scripts.case_builder \
  --case vitals \
  --cycles 1 \
  --transcript "$TRANSCRIPT_DIR/vitals.json" \
  --patient "$PATIENT_ID" --render

echo "All single command tests completed!"
