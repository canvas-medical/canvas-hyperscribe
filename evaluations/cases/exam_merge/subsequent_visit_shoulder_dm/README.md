# subsequent_visit_shoulder_dm

The first exam-merge case, captured from `scribeqa-playground` running
`hyperscribe@2026-08-30 v0.4.56` with `ScribeExamTemplateMerge` enabled for all three
kinds. A general-medicine follow-up covering right shoulder pain, uncontrolled type 2
diabetes, and new depression, generated under the **Subsequent Visit** template.

This case is the harness's own regression fixture. Its numbers are known-good and
pinned in `tests/evaluations/exam_merge/test_invariants.py`, so if they change, suspect
the harness before the note.

| | Template | Encounter | Floor | Final | Title match |
|---|---|---|---|---|---|
| ROS | 7 | 9 | 13 | 10 | 3 / 9 |
| Physical Exam | 6 | 10 | 13 | 10 | 3 / 10 |

ROS floor-versus-final ledger: 3 improved, 1 regressed, 3 consolidated, 6 unchanged.

## What it exercises

- **A real M8 regression.** The floor correctly took the encounter's "No rashes" for
  SKIN. The refinement reverted it to the template's broader "Denies lumps/bumps, rash,
  or skin tear" and flipped `updated` to false, adding two denials the visit never
  established.
- **Good consolidation that must not be flagged as a defect.** `General→CONSTITUTIONAL`,
  `Cardiovascular→CARDIAC`, `Gastrointestinal→DIGESTIVE`, `Lungs→PULMONARY`, and flat
  affect moved out of NEUROLOGIC into PSYCH. M4 reports these as warnings with high
  content survival, not failures.
- **Clause-level over-attestation invisible to Layer 1.** The CARDIAC row is
  `updated: true` yet carries "shortness of breath with exertion", which the transcript
  contradicts ("I do get winded on the stairs"), and "swelling in the legs", which the
  note's own PE contradicts ("Trace bilateral ankle edema"). Only `--judge` sees these.
- **A low deterministic match rate**, 33% and 30%, which is the label-disagreement
  problem that makes the floor weaker than intended.

## Files

| File | Notes |
|---|---|
| `transcript.json` | The finalized transcript, 247 items. |
| `visit_templates.json` | The full `VisitTemplates` secret value, all five templates. |
| `summary.json` | What `GET /summary` returned. |
| `runs/` | Additional summaries for the reliability layer. Empty until captured. |
| `report/` | Generated output, gitignored. Safe to delete. |
| `judged_baseline_2026-08-30.*` | Judge run on `claude-sonnet-4-5`, manually audited. |
| `judged_baseline_opus5_2026-08-30.*` | Judge run on `claude-opus-5`, manually audited. The reference run. |

`summary.json` carries `selected_template_name`, `note_data`, and `commands`. Omitted
from the captured artifact: `recommendations`, `unmatched_conditions`,
`diagnosis_suggestions`, `raw_response`, and `raw_normalized_response`. All are outside
this harness's scope, and `raw_normalized_response` alone is several hundred lines of
ICD-10 alternative codings. If a future layer needs them, recapture rather than
reconstruct.

## Capturing more runs

Generate the same transcript again on the instance, then copy the summary JSON out of
the debug cache app into `runs/run_N.json`. Only the summary is needed; the transcript
and templates are identical by construction. `GET /summary` returns exactly this shape
but is staff-session gated, so this step is manual.

## Running it

```bash
DJANGO_SETTINGS_MODULE=settings uv run python -m scripts.exam_merge_eval \
    --case evaluations/cases/exam_merge/subsequent_visit_shoulder_dm

# add the clause-level judge (needs VendorTextLLM / KeyTextLLM from local_env.sh)
DJANGO_SETTINGS_MODULE=settings uv run python -m scripts.exam_merge_eval \
    --case evaluations/cases/exam_merge/subsequent_visit_shoulder_dm --judge

# once runs/ has two or more summaries
DJANGO_SETTINGS_MODULE=settings uv run python -m scripts.exam_merge_eval \
    --case evaluations/cases/exam_merge/subsequent_visit_shoulder_dm --reliability
```

## The audited judge baseline

`judged_baseline_2026-08-30.json` and `.csv` hold a real `--judge` run whose every
unsupported assertion was checked by hand against the transcript. No false positives
were found. Keep it as the reference for what good output looks like, since the judge is
not deterministic and a fresh run will not match it clause for clause.

| | ROS | Physical Exam |
|---|---|---|
| assertions | 39 | 47 |
| unsupported | 15 (38%) | 6 (13%) |
| template-sourced and unsupported | 13 | 6 |
| contradictions | 2 | 0 |

It confirms the reason this layer exists. Layer 1 reports `template_sourced_rows = 0`
for the physical exam, because every PE row is marked `updated: true`. The judge found
six unearned template clauses living inside those rows: "Well developed", "Nourished",
"S1 normal", "S2 normal", "No clubbing", and "No cyanosis". Row-level provenance cannot
see any of them.

Two catches worth knowing about, neither of which was predicted when the harness was
designed:

- ROS DIGESTIVE "Denies abdominal pain" is contradicted by PE Abdomen's "mild epigastric
  tenderness to palpation".
- ROS NEUROLOGIC "No dizziness" has no transcript support at all. The doctor asked "Any
  headaches, dizziness, vision changes?" and the patient answered "No headaches.
  Vision's fine." Dizziness was never addressed, and Nabla filled it in.

## Two judge models on the same artifact

`JUDGE_MODEL` is `claude-opus-5`, deliberately not the `claude-sonnet-4-5` that produces
the merge, and pinned by a test so it cannot drift back. Both baselines are kept because
the comparison is itself evidence about how much the judge's model matters.

| | sonnet-4-5 | opus-5 |
|---|---|---|
| ROS assertions | 39 | 40 |
| ROS unsupported | 15 (38%) | 16 (40%) |
| ROS contradictions | 2 | 5 |
| PE assertions | 47 | 47 |
| PE unsupported | 6 (13%) | 7 (15%) |

They agree on substance. Most of the apparent differences are clause-splitting
granularity: sonnet emits "Denies muscle aches or cramps" where opus splits it in two,
and "Nourished" against "Well nourished". Opus found one thing sonnet did not, and it is
a good catch:

- PE HEENT "Head atraumatic" is unsupported. The clinician said "HEENT exam unremarkable"
  and then enumerated only ears, nose, throat, and neck. Nothing examined the head. This
  is the only unsupported assertion in the whole note that is not template boilerplate,
  so it is a Nabla fabrication rather than an over-attestation.

Opus also reasoned about downstream consequence in a way sonnet did not. On the leg-swelling
contradiction it noted that amlodipine was started this visit with ankle swelling named as
the monitored side effect, so a false ROS baseline will corrupt the four-week recheck.

One schema wrinkle to tighten later: opus twice used `contradicted_by` as a
cross-reference between two ROS rows making mutually inconsistent claims, rather than
naming a section that positively refutes the assertion. Both findings were correct; the
field was stretched. It also hedged honestly where a call was arguable, saying of the
callus-versus-"denies lumps/bumps" conflict that the "contradiction is arguable but the
assertion is unsupported regardless."

## Reaching 4.7+ models at all

`LlmAnthropic` cannot talk to any Anthropic model newer than 4.6. It always sends
`temperature`, which those models reject with a 400, and it reads the response as
`content[0]["text"]`, which is a `thinking` block on those models, so the client sees an
empty string and burns its retries. `Constants.ANTHROPIC_REASONING_TEXT` compounds this
by pointing at `claude-opus-4-1-20250805`, which no longer exists.

The judge works around both from the evaluation layer via
`HelperSyntheticJson(..., anthropic_4_7_compat=True)`, which drops `temperature` and sets
`thinking` to disabled on that one client instance. Nothing in `hyperscribe/` changes, so
the deployed plugin is untouched. The cost is that the judge runs without extended
thinking. Fixing the plugin's client is the real answer and is a separate decision.
