#!/bin/bash

# Script to run case_builder for all single command transcripts

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Define paths relative to script directory
TRANSCRIPT_DIR="$SCRIPT_DIR/transcripts"
CHART_DIR="$SCRIPT_DIR/limited_caches"

# Change to project root (two levels up from script directory)
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "Project root     : $PROJECT_ROOT"
echo "Using transcripts: $TRANSCRIPT_DIR"
echo "Using charts     : $CHART_DIR"
echo ""

echo "--- common commands ---"
echo "run adjust_prescription..."
uv run python -m scripts.case_builder \
  --case adjust_prescription \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/adjust_prescription.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run allergy..."
uv run python -m scripts.case_builder \
  --case allergy \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/allergy.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run assess..."
uv run python -m scripts.case_builder \
  --case assess \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/assess.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run close_goal..."
uv run python -m scripts.case_builder \
  --case close_goal \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/close_goal.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run diagnose..."
uv run python -m scripts.case_builder \
  --case diagnose \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/diagnose.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run family_history..."
uv run python -m scripts.case_builder \
  --case family_history \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/family_history.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run follow_up..."
uv run python -m scripts.case_builder \
  --case follow_up \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/follow_up.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run goal..."
uv run python -m scripts.case_builder \
  --case goal \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/goal.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run history_of_present_illness..."
uv run python -m scripts.case_builder \
  --case history_of_present_illness \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/history_of_present_illness.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run imaging_order..."
uv run python -m scripts.case_builder \
  --case imaging_order \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/imaging_order.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run immunization_statement..."
uv run python -m scripts.case_builder \
  --case immunization_statement \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/immunization_statement.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run immunize..."
uv run python -m scripts.case_builder \
  --case immunize \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/immunize.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run instruct..."
uv run python -m scripts.case_builder \
  --case instruct \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/instruct.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run lab_order..."
uv run python -m scripts.case_builder \
  --case lab_order \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/lab_order.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run medical_history..."
uv run python -m scripts.case_builder \
  --case medical_history \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/medical_history.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run medication..."
uv run python -m scripts.case_builder \
  --case medication \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/medication.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run perform..."
uv run python -m scripts.case_builder \
  --case perform \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/perform.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run plan..."
uv run python -m scripts.case_builder \
  --case plan \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/plan.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run prescription..."
uv run python -m scripts.case_builder \
  --case prescription \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/prescription.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run reason_for_visit..."
uv run python -m scripts.case_builder \
  --case reason_for_visit \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/reason_for_visit.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run refer..."
uv run python -m scripts.case_builder \
  --case refer \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/refer.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run refill..."
uv run python -m scripts.case_builder \
  --case refill \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/refill.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run remove_allergy..."
uv run python -m scripts.case_builder \
  --case remove_allergy \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/remove_allergy.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run resolve_condition..."
uv run python -m scripts.case_builder \
  --case resolve_condition \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/resolve_condition.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run stop_medication..."
uv run python -m scripts.case_builder \
  --case stop_medication \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/stop_medication.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run surgery_history..."
uv run python -m scripts.case_builder \
  --case surgery_history \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/surgery_history.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run task..."
uv run python -m scripts.case_builder \
  --case task \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/task.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run update_diagnose..."
uv run python -m scripts.case_builder \
  --case update_diagnose \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/update_diagnose.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run update_goal..."
uv run python -m scripts.case_builder \
  --case update_goal \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/update_goal.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "run vitals..."
uv run python -m scripts.case_builder \
  --case vitals \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/vitals.json" \
  --chart "$CHART_DIR/for_single_command.json"

echo "--- questionnaires ---"
echo "run questionnaire: tobacco..."
uv run python -m scripts.case_builder \
  --case questionnaire \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/questionnaire_tobacco.json" \
  --chart "$CHART_DIR/questionnaire_tobacco.json"

echo "run review of systems: brief..."
uv run python -m scripts.case_builder \
  --case review_of_systems \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/review_of_systems_brief.json" \
  --chart "$CHART_DIR/review_of_systems_brief.json"

echo "run Structured Assessment: COPD..."
uv run python -m scripts.case_builder \
  --case structured_assessment \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/structured_assessment_copd.json" \
  --chart "$CHART_DIR/structured_assessment_copd.json"

echo "run Physical Exam: Respiratory..."
uv run python -m scripts.case_builder \
  --case physical_exam \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/physical_exam_respiratory.json" \
  --chart "$CHART_DIR/physical_exam_respiratory.json"

echo "run Physical Exam: Pediatric Vitals..."
uv run python -m scripts.case_builder \
  --case physical_exam \
  --cycles 1 \
  --overwrite \
  --transcript "$TRANSCRIPT_DIR/physical_exam_pediatric_vitals.json" \
  --chart "$CHART_DIR/physical_exam_pediatric_vitals.json"

echo "All single command tests completed!"
