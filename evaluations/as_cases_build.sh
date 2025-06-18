#!/bin/bash
uv run python case_builder.py \
  --patient patient_id \
  --case audio_with_questionnaires \
  --group common \
  --type general \
  --cycles 10 \
  --transcript ~/canvas-hyperscribe/evaluations/audio2transcript/expected_json/audio_with_questionnaires.json

uv run python case_builder.py \
  --patient patient_id \
  --case audio_with_lab_order_for_hypertension \
  --group common \
  --type general \
  --cycles 10 \
  --transcript ~/canvas-hyperscribe/evaluations/audio2transcript/expected_json/audio-with-lab-order-for-hypertension.json

uv run python case_builder.py \
  --patient patient_id \
  --case chronic_cough \
  --group common \
  --type general \
  --cycles 20 \
  --transcript ~/canvas-hyperscribe/evaluations/audio2transcript/expected_json/chronic_cough.json

uv run python case_builder.py \
  --patient patient_id \
  --case diabetes_med_adjustment \
  --group common \
  --type general \
  --cycles 10 \
  --transcript ~/canvas-hyperscribe/evaluations/audio2transcript/expected_json/diabetes_med_adjustment.json




  