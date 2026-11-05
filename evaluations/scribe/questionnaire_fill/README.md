# Questionnaire fill evaluation

Measures the accuracy, reliability, latency and cost of drafting questionnaire answers from
a visit transcript. Runs the shipping code path against real Opus 5 calls, with only the ORM
stubbed.

```bash
export ANTHROPIC_API_KEY=sk-ant-...

uv run scripts/eval_questionnaire_fill.py --self-test   # check the checker, no API calls
uv run scripts/eval_questionnaire_fill.py --inject      # failure paths, no API calls
uv run scripts/eval_questionnaire_fill.py --dry-run     # list cases and chunk counts
uv run scripts/eval_questionnaire_fill.py --runs 3      # the real thing, ~$0.50
uv run scripts/eval_questionnaire_fill.py --case never_discussed
uv run scripts/eval_questionnaire_fill.py --runs 3 --out report.md
```

Always run `--self-test` and `--inject` before trusting a measured run. They cost nothing and
they are the difference between a harness and a rubber stamp.

## Why a script and not a pytest suite

`conftest.py:108` pulls the whole legacy `Settings` env (`APISigningKey` and friends) into
collection for anything matching its eval filenames. This needs only `ANTHROPIC_API_KEY`. It
also emits a report rather than a verdict, which is the point: thresholds should come from
measured behaviour, not from a guess made before measuring.

`--self-test` and `--inject` are the parts that genuinely pass or fail, and they are the ones
worth wiring into CI once the numbers settle.

## What the metrics mean

| Metric | Reading it |
|---|---|
| **fabrication** | The transcript did not support an answer and the model gave one. The release-blocking class: it reaches a signed note looking exactly like a real answer. |
| **denial_confusion** | A topic that never came up recorded as an explicit denial, or the reverse. Counted separately from fabrication because on a scored screener a spurious "Not at all" silently lowers the total rather than leaving a visible gap. |
| **band_error** | Right that it was discussed, wrong severity option. Wrong but grounded, and still moves a score. |
| **wrong_value** | Free-text or integer answer that does not match. Watch for silent rounding. |
| **over_abstention** | The transcript supported an answer and the model declined. Makes the feature useless, not dangerous. |
| **evidence integrity** | Whether each cited quote actually appears in the turn it claims to come from. Nothing in production checks this; see the known gap below. |
| **stability** | Same case, several runs, same answers? There is no temperature control and adaptive thinking is nondeterministic. |
| **cache hit rate** | Share of input tokens served from cache. Near zero on multi-chunk cases would mean the chunking is costing money instead of saving it. |

## Adding a case

One file per case in `cases/`, one failure mode per case. The questionnaire is in the shape
`resolve_questionnaire_definition` returns; the transcript is in `TranscriptItem` shape and
**must carry real `item_id`s**, because the grounding gate keys on them entirely.

```json
{
  "id": "phq9_explicit_denial",
  "probes": "one sentence on what this case is for",
  "questionnaire": { "questionnaire_dbid": 1, "questionnaire_name": "PHQ-9",
                     "is_scored": true, "scoring_function_name": "sum", "questions": [...] },
  "transcript": [ {"item_id": "t1", "speaker": "DOCTOR", "text": "...",
                   "start_offset_ms": 0, "end_offset_ms": 2000} ],
  "expected": {
    "10": {"status": "denied", "option_dbid": 100},
    "11": {"status": "not_assessed"}
  }
}
```

Ground truth keys, all optional except `status`:

| Key | Use |
|---|---|
| `option_dbid` | Single choice, the one right answer. |
| `acceptable_option_dbids` | Where a neighbouring band is genuinely defensible. Prevents a real ambiguity being scored as an error. |
| `option_dbids` | Multiselect, the exact expected set. |
| `acceptable_statuses` | Where `answered` and `denied` are both reasonable. |
| `value` / `acceptable_values` | Integer or exact text. |
| `value_contains` | Free text, substring match after normalising punctuation and case. |
| `note` | Why this is the right answer. Write one whenever the label is not obvious. |

**Label carefully, and read the failures rather than the totals.** The first run of this suite
reported two band errors that turned out to be my own mislabelling: I had marked "I quit three
years ago" as a current smoker, and scored "a glass of wine once a week" as Occasional when
Weekly is the literal reading. The model was right both times. Ground truth is the hard part
of this eval, and an aggregate number will happily hide a bad label.

## Known gap this suite measures but does not fix

`_apply_grounding_gate` verifies that a cited `item_id` exists in the transcript. It never
checks that the `quote` appears in that turn's text, and it uses `any()`, so a single valid
`item_id` carries an item whose other citations are invented. `--inject` proves the path is
reachable: a fabricated quote attached to a real turn passes the gate.

Measured evidence integrity has been 100%, so the model is not currently exploiting it. The
fix, if it ever slips, is to verify quotes against the cited turn's text and require every
cited turn to resolve rather than any.

## What this cannot see

The harness stubs `load_questionnaire`, so it never touches the ORM, the RestrictedPython
sandbox, or the 30-second `Http.post` wall. Both production bugs in this feature so far lived
in exactly those places and were invisible to `canvas validate` as well. On-instance
spot-checks remain necessary; see the plan for the six that matter.
