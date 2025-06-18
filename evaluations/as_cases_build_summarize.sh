#!/bin/bash
uv run python case_builder.py --case fatigue_case --delete

uv run python case_builder.py \
  --patient patient_id \
  --case fatigue_case \
  --group common \
  --type general \
  --cycles 1 \
  --transcript ~/canvas-hyperscribe/evaluations/audio2transcript/expected_json/fatigue.json \
  --render

uv run python case_builder.py --case fatigue_case --summarize