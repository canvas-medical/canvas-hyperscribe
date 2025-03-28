TRANSCRIPTS_DIRECTORY="$PATH_TO_REPO/canvas-hyperscribe/evaluations/transcripts"

# TODO: Avoid building cases that are already present

uv run python case_builder.py \
  --group interviewing \
  --type situational \
  --case simple_hpi_dialogue \
  --transcript "$TRANSCRIPTS_DIRECTORY/simple_hpi_dialogue.json" \
  --patient 9366aa4c0e76457d94c9dedfc1d8dfab

uv run python case_builder.py \
  --group prescribing_intent \
  --type situational \
  --case peds_aom_rx_yes_allergy \
  --transcript "$TRANSCRIPTS_DIRECTORY/peds_aom_vague_rx.json" \
  --patient b5f5858afe76448d92772c1f5c3e9f7f

uv run python case_builder.py \
  --group prescribing_intent \
  --type situational \
  --case peds_aom_rx_no_allergy \
  --transcript "$TRANSCRIPTS_DIRECTORY/peds_aom_vague_rx.json" \
  --patient cf1cd4b18e2e46229397f6696ba06933
