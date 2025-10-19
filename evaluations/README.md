Hyperscribe Evaluations
=======================

### Description
The [hyperscribe](../hyperscribe) plugin has five essential steps:

* transcript the audio into a discussion, identifying the speakers and what they say
* then:
  * extract from the discussion a set of instructions, a plain English description of a Canvas command
  * transform an instruction into a data structure close to Canvas command parameters
  * create the Canvas command based on the parameters
* and:
  * update the staged questionnaires in the considered note based on the discussion

The aim is to provide a continuous validation of the Hyperscribe plugin through two approaches:

* a test suite run with `pytest` that checks step by step the coherence and the value of the plugin
* a case suite run with [`case_runner.py`](../scripts/case_runner.py) script that executes an end-to-end scenario and evaluate it against a rubric

The `pytest` approach is designed to help understand and improve the plugin deep and narrowly.

The rubric approach is designed to offer an overall quality benchmark of the plugin. Currently, the [`case_runner.py`](../scripts/case_runner.py) script
doesn't go further than executing the plugin code using the case from the transcript to the production of the commands and the `summary` files.

#### Situational and case evaluations
The evaluation tests are separated into two categories:
* ___situational___ evaluation: this checks the behavior of the Hyperscribe code against a single step, possibly through several cycles
* ___case___ evaluation: this checks the behavior of the Hyperscribe code through all the steps and cycles

The _case builder_ commands generate the drafts of the evaluation cases. They are described later in this document.

#### Folders structure

The _situational_ evaluations are in a folder related to the covered step:
  * `situational/audio2transcript`
  * `situational/transcript2instructions`
  * `situational/instruction2parameters`
  * `situational/parameters2command`
  * `situational/staged_questionnaires`

The files of the `audio2transcript` step are stored as:
* `theSituationName/audios` for the audio files
* `theSituationName/audio2transcript.json` for the expected transcripts

For the other steps, for each cycle, the input and the expected output are stored in `theSituationName.json` files.


### Run evaluation tests

The evaluation tests are run as `pytest` tests.

The basic idea is that all figures or dates should be exactly the same from one run to another one.
It is possible to ignore the value of a key when comparing the expected output and the actual output by setting it to `>?<`
(see [here](./helper_evaluation.py) the method `json_nuanced_differences` using the constant `IGNORED_KEY_VALUE` defined in
[`constants.py`](./constants.py)).

The following parameters can be used to configure the evaluation test:

- `--evaluation-difference-levels` – Specifies the expected level of accuracy for any text value (`minor`, `moderate`, `severe`, `critical` as
  defined in [`constants.py`](./constants.py) as `DIFFERENCE_LEVELS`).
- `--patient-uuid` – Identifies the patient to run the evaluation test against.
- `--print-logs` – Print the logs on the standard output at the end of the tests.
- `--store-logs` – Store the logs in the configured AWS S3 bucket.
- `--end2end` – Run the _case_ tests in one shot (otherwise, they are run as _situational_ tests).


```shell
# list all the existing tests
uv run pytest --collect-only -q evaluations/

# run a specific situational test
uv run pytest -v evaluations/test_audio2transcript.py::test_audio2transcript[the_test_as_shown_with_the_tests_collection]

# run a specific case test
uv run pytest -v --end2end evaluations/test_end2end.py::test_end2end[the_test_as_shown_with_the_tests_collection]

# run ALL situational tests for the step transcript2instructions
uv run pytest -v evaluations/test_transcript2instructions.py

# run ALL situational tests
uv run pytest -v evaluations/

# run ALL case tests
uv run pytest -v --end2end evaluations/

# run all tests of the step transcript2instructions for cases or situation starting with xxxx
uv run pytest -vv evaluations/ -k "test_detail_transcript2instructions[xxxx"
```

### Create evaluation tests

To be able to create evaluation codes locally, in addition to the `CANVAS_SDK_DB_...` as defined in the [README.md](../hyperscribe/README.md), create the environment variables:

```shell
export VendorTextLLM="..." # OpenAI, Google, Anthropic...
export KeyTextLLM="..."
export VendorAudioLLM="..." # OpenAI, Google, Anthropic...
export KeyAudioLLM="..."
export StructuredReasonForVisit="y" or "n"
export AuditLLMDecisions="y" or "n"
export APISigningKey="..."
export CUSTOMER_IDENTIFIER="local" # the canvas_instance value
export CommandsPolicy="n"
export CommandsList=""
```

The logs will be sent to the `AWS S3 bucket` if the following environment variables are set:

```shell
export AwsKey="..."
export AwsSecret="..."
export AwsRegion="..."
export AwsBucketLogs="..."
```

In addition, if the `AuditLLMDecisions` is set, an audit of the LLM decisions is run at the end of the evaluation and saved in the AWS S3 bucket provided.

The logs are saved following the folder structure, with the top-level `hyperscribe-{canvas_instance}` needing to match exactly the IAM User whose `AwsKey` and `AwsSecret` are set in secrets:

```shell
AwsBucket
      |- hyperscribe-{canvas_instance}
           |- audits - all audit files
           |- finals - concatenated logs of each cycle
           |- llm_turns - log of each LLM communication
           |- partials - logs of each step
```

#### Case builders

The case builders are scripts that run the `Hyperscribe` code on different kind of inputs and generate a `case` (i.e., coherent and normalized set of
inputs) and the outputs for each step.
It is important to note that output could/should be modified to reflect the actual expected result of each step.

The case builders always generate a summary of the commands as an HTML page saved in the `/tmp` directory provided at the end.

The cases are stored either in the file system or a database, SQLite or PostgreSQL.

The PostgreSQL option is the preferred one and is the only documented below.

This assumes the following environment variables are correctly set:
```shell
export EVALUATIONS_DB_NAME="..."
export EVALUATIONS_DB_USERNAME="..."
export EVALUATIONS_DB_PASSWORD="..."
export EVALUATIONS_DB_HOST="..."
export EVALUATIONS_DB_PORT=000
```


#### From Audio to commands

Based on a set of `mp3` files, a `case` and its outputs can be created using:

```shell
uv run python -m scripts.case_builder \
  --patient patient_uuid \
  --case the_case \
  --render \
  --combined \
  --mp3 "file/path/to/file_01.mp3" \
  "file/path/to/file_02.mp3" \
  "file/path/to/file_03.mp3"
```

The `combined` flag instructs the case builder to first combine the mp3 files in one audio first.

Without it, the case builder will perform as many cycles as files, using the result of each cycle as input to the next, mimicking the real behavior.

If the `render` flag is set, the effects of the commands, result of the last cycle, will be sent to the UI.

#### From Transcript to commands

Based on a `json` file, transcript of the conversation, a `case` and its outputs can be created using:

```shell
uv run python -m scripts.case_builder \
  --patient patient_uuid \
  --case the_case \
  --render \
  --cycles 3 \
  --transcript "file/path/to/file.json"
```

The flag `cycles` instructs the case builder to perform as many cycles, using the result of each cycle as input to the next, mimicking the real
behavior.

Like previously, if the `render` flag is set, the effects of the commands, result of the last cycle, will be sent to the UI.

#### From Tuning data to commands

Based on a set of `mp3`, recordings of a discussion through the `hyperscribe-tuning` plugin and its `json` file, limited cache of the patient data at
the start of the recording, a `case` and its outputs can be created using:

```shell
uv run python -m scripts.case_builder \
  --case the_case \
  --tuning-json "file/path/to/file.json" \
  --tuning-mp3 "file/path/to/file_01.mp3" \
  "file/path/to/file_02.mp3" \
  "file/path/to/file_03.mp3"
```

This case builder based on the tuning data has the same behavior as the case builder based on audio files, except that it has no `render` flag.

#### Storing the cases and the run results

To store the results in a PostGreSQL database, add to the environment the variables:

```shell
export EVALUATIONS_DB_NAME="..."
export EVALUATIONS_DB_USERNAME="..."
export EVALUATIONS_DB_PASSWORD="..."
export EVALUATIONS_DB_HOST="..."
export EVALUATIONS_DB_PORT=000
```

The database schema defined in [hyperscribe.sql](./datastores/postgres/hyperscribe.sql) should be present before running any case builder.

The table `case` stores the cases, and the table `generated_note` stores the outputs for each step, with the result output in the field `note_json`.

### Realworld cases generation

Based on the data saved through the Hyperscribe tuning mode, realworld cases can be generated either:

* as a unique case, using the recording entirely, or
* as topical cases, using the parts of the recording for detected topics

The realworld data is always anonymized while keeping the coherence of the encounter.

To generate the realworld cases, accessing to the tuning data requires the following environment variables:

```shell
export CUSTOMER_IDENTIFIER="theCustomerIdentifier"
export AwsKey="theAwsKey"
export AwsSecret="theAwsSecret"
export AwsRegion="theAwsRegion"
export AwsBucketLogs="theAwsBucketLogs"
export AwsBucketTuning="theAwsBucketTuning"
```

The case builders will first retrieve the audio and the limited cache JSON files and store them locally: __it is important to note that the files
have HPI information__.

The de-identification is done on later and not in-place.

The table `real_world_case` stores the information related to the generated cases.

### Full realworld cases generation

Based on the full encounter, a `case` and its outputs can be created using:

```shell
uv run python -m scripts.case_builder \
  --direct-full \
  --patient "thePatientUUID" \
  --note "theNoteUUID" \
  --cycle_duration 60 \
  --force_rerun \
  --path_temp_files "path/to/store/temporary/phi/data/"
```

The `--force_rerun` forces the script to regenerate the case, this option is recommended.
The `--force_refresh` forces the script to retrieve the files from AWS and to run all the steps, involving the LLM, before the case generation, this option is not
recommended.

### Topical realworld cases generation

Based on the full encounter, the case builder will identify when the conversation changes of topics and generate as many `cases` as identified topics.
The topics are continuous set of sentences related to the same medical topic (nonmedical dialogues are kept but ignored from a topic detection point
of view).

The set of `cases` and their outputs can be created using:

```shell
uv run python -m scripts.case_builder \
  --direct-split \
  --patient "thePatientUUID" \
  --note "theNoteUUID" \
  --cycle_duration 60 \
  --force_rerun \
  --path_temp_files "path/to/store/temporary/phi/data/"
```

### Batch realworld cases generation

For a specific customer, all recorded encounters through the Hyperscribe tuning mode can be used to generate topical cases using:

```shell
uv run python -m evaluations.case_builders.realworld_case_orchestrator \
    --customer "theCustomer" \
    --cycle_duration 60 \
    --cycle_overlap 60 \
    --max_workers 6 \
    --path_temp_files "path/to/store/temporary/phi/data/"
```

The command ignores the encounters with a generated case.

At the end of the script is a summary list of the successful and failed generations:
```text
================================================================================
summary
================================================================================
✅ [001] Patient: thePatientUUID1, Note: theNoteUUID1 (exit code: 0)
❌ [002] Patient: thePatientUUID2, Note: theNoteUUID2 (exit code: 1)
✅ [003] Patient: thePatientUUID3, Note: theNoteUUID3 (exit code: 0)
✅ [004] Patient: thePatientUUID4, Note: theNoteUUID4 (exit code: 0)
--------------------------------------------------------------------------------
Total: 4 | Success: 3 | Failed: 1
================================================================================

```

### Utility scripts

#### Count Notes

The [`count_notes.py`](../scripts/count_notes.py) script queries the hyperscribe-logs S3 bucket to count notes by date and customer. It outputs a wide-format CSV table with one row per date and one column per customer. Use `--all-customers` and `--all-dates` flags to discover all available data, or specify specific customers and date ranges.

```shell
# Query all customers across all dates
uv run python scripts/count_notes.py --all-customers --all-dates

# Query specific customers for a date range
uv run python scripts/count_notes.py production staging --start-date 2025-10-01 --end-date 2025-10-07

# Use --help for full usage details
uv run python scripts/count_notes.py --help
```

#### Tuning Case Count

The [`tuning_case_count.py`](../scripts/tuning_case_count.py) script analyzes the hyperscribe-tuning-case-data S3 bucket to count patients, notes, and audio chunks. It outputs a CSV table sorted by note count descending. Use `--all-customers` to discover and analyze all customer prefixes.

```shell
# Query all customers
uv run python scripts/tuning_case_count.py --all-customers

# Query specific customer prefix
uv run python scripts/tuning_case_count.py hyperscribe-production

# Use --help for full usage details
uv run python scripts/tuning_case_count.py --help
```
