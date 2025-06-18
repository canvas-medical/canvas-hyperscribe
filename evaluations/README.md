Hyperscribe Evaluations
=======================

The [hyperscribe](../hyperscribe) plugin has five essential steps:

* transcript the audio into a discussion, identifying the speakers and what they say
* extract from the discussion a set of instructions, a plain English description of a Canvas command
* transform an instruction into a data structure close to Canvas command parameters
* create the Canvas command based on the parameters
* update the staged questionnaires in the considered note based on the discussion

The evaluation tests are designed to validate each of these steps.

The convention is to have:

- a folder where to store tests for each step ([`evaluations/audio2transcript`](./audio2transcript), [
  `evaluations/transcript2instructions`](./transcript2instructions)...)
- a test file to run the stored tests of each step ([`test_audio2transcript.py`](test_audio2transcript.py), [
  `test_transcript2instructions.py`](test_transcript2instructions.py)...)
- all test files of cases built with the case builders are stored in a subfolder to the [`cases`](./cases) directory.

The JSON files store, for each cycle, the input and the expected output for the considered step.

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

Among standard `pytest` parameters, `-k` is useful as it allows targeting tests of specific cases.

```shell
# run all evaluation tests for the patient patient_uuid
uv  run pytest -v evaluations --patient-uuid patient_uuid

# run the test the_case defined for the step audio2transcript, 
# accepting all differences minor, moderate and severe
uv  run pytest -v evaluations/test_audio2transcript.py -k the_case --evaluation-difference-levels "minor,moderate,severe"

# run the test the_case defined for the step instruction2parameters 
# for the patient patient_uuid
uv  run pytest -v evaluations/test_instruction2parameters.py -k the_case --patient-uuid patient_uuid

# run all tests for the step parameters2command 
# for the patient patient_uuid
uv  run pytest -v evaluations/test_parameters2command.py --patient-uuid patient_uuid

# run all tests for the step transcript2instructions 
# for the patient patient_uuid
uv  run pytest -v evaluations/test_transcript2instructions.py --patient-uuid patient_uuid

# run the test the_case for the step staged_questionnaires 
uv  run pytest -v evaluations/test_staged_questionnaires.py -k the_case

# run all steps for a specific case the_case
uv  run pytest -v evaluations -k the_case

# run a specific test
uv  run pytest -vv evaluations/test_parameters2command.py::test_parameters2command[the_case_cycle_007]

# run from end to end the case the_case
uv  run pytest evaluations/test_end2end.py::test_end2end[the_case]
```

### Create evaluation tests

To be able to create evaluation codes locally, in addition to the `CANVAS_SDK_DB_...` as defined in the [README.md](../hyperscribe/README.md), create
the environment variables:

```shell
export VendorTextLLM="..." # OpenAI, Google, Anthropic...
export KeyTextLLM="..."
export VendorAudioLLM="..." # OpenAI, Google, Anthropic...
export KeyAudioLLM="..."
export ScienceHost="..."
export OntologiesHost="...."
export PreSharedKey="...."
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

In addition, if the `AuditLLMDecisions` is set, an audit of the LLM decisions is run at the end of the evaluation and saved in the AWS S3 bucket
provided.

The logs are saved following the folder structure, with the top-level `hyperscribe-{canvas_instance}` needing to match exactly the IAM User whose
`AwsKey` and `AwsSecret` are set in secrets:

```shell
AwsBucket
      |- hyperscribe-{canvas_instance}
           |- audits - all audit files
           |- finals - concatenated logs of each cycle
           |- llm_turns - log of each LLM communication
           |- partials - logs of each step
```

#### Case builders

The case builders are scripts that create all evaluation tests from end to end.

The evaluation tests are stored in the [cases](cases) directory, one subdirectory per case.

These evaluations of a case are run all at once with:

```shell
uv run pytest evaluations/test_end2end.py::test_end2end[the_case]
```

The files created are:

- the `audios` folder, containing the `mp3` files used for the step `audio2transcript`
- the `audio2transcript.json` file, containing the input and the expected output for the step `audio2transcript`
- the `transcript2instructions.json` file, containing the input and the expected output for the step `transcript2instructions`
- the `instruction2parameters.json` file, containing the input and the expected output for the step `instruction2parameters`
- the `parameters2command.json` file, containing the input and the expected output for the step `parameters2command`
- the `staged_questionnaires.json` file, containing the input and the expected output for the questionnaires updates
- the `summary_initial.json` file, containing the summarized commands
- the `summary_revised.json` file, containing the summarized commands which would be revised
- the `summary.html` file, HTML file to display the summarized commands based on the `summary_revised.json` file ; it can be updated with the command
  `uv run python case_builder.py --case the_case --summarize`

Note that when removing the case files with the command `uv run python case_builder.py --case the_case --delete [--audios]`, the files `summary.html`
and `summary_revised.json` are not removed.

#### From Audio to commands

Based on a set of `mp3` files, a set (i.e., covering all steps) of evaluation tests (also called `case`) can be created using:

```shell
uv run python case_builder.py \
  --patient patient_uuid \
  --case the_case \
  --group common \
  --type general \
  --render \
  --combined \
  --mp3 "file/path/to/file_01.mp3" \
  "file/path/to/file_02.mp3" \
  "file/path/to/file_03.mp3"
```

The `combined` flag instructs the case builder to first combine the mp3 files in one audio first.

Without it, the case builder will perform as many cycles as files, using the result of each cycle to the next, mimicking the real behavior.


```shell
# run the tests for the_case
uv  run pytest -v evaluations/test_end2end.py::test_end2end[the_case]
```

Note also that on the first step (`audio2transcript`):

- all `mp3` files are saved in the `evaluations/cases/the_case/audios` folder, all files are named
  `cycle_\d{3}_\d{2}`, the first number being the cycle, the second number being the chunk used during the cycle (all numbers starting from 0).
- if a cycle has the transcript already done, the step is not performed again.

On the second step (`transcript2instructions`):
- the `uuid` of the instructions is by default set to `>?<`
- the instruction order of different types is ignored

If the `render` flag is set, the effect of the commands, result of the last cycle, will be sent to the UI.

#### From Transcript to commands

Based on a `json` file, transcript of the conversation, a set (i.e. covering all steps except the first one) of evaluation tests can be created using:

```shell
uv run python case_builder.py \
  --patient patient_uuid \
  --case the_case \
  --group common \
  --type general \
  --render \
  --cycles 3 \
  --transcript "file/path/to/file.json"
```

The flag `cycles` instructs the case builder to perform as many cycles, using the result of each cycle to the next, mimicking the real behavior.

Like previously, on the step `transcript2instructions`:

- the `uuid` of the instructions is by default set to `>?<`
- the instruction order of different types is ignored

If the `render` flag is set, the effect of the commands, result of the last cycle, will be sent to the UI.

#### From Tuning data to commands

Based on a set of `mp3`, recordings of a discussion through the `hyperscribe-tuning` plugin and its `json` file, limited cache of the patient data at
the start of the recording, a set of evaluation tests can be created using:

```shell
uv run python case_builder.py \
  --case the_case \
  --group common \
  --type general \
  --tuning-json "file/path/to/file.json" \
  --tuning-mp3 "file/path/to/file_01.mp3" \
  "file/path/to/file_02.mp3" \
  "file/path/to/file_03.mp3"
```

This case builder based on the tuning data has the same behavior as the case builder based on audio files, except that it has no `render` flag.

#### Storing the cases and the run results

When creating a `case` by running the [`case_builder.py`](../case_builder.py) script, a file created/updated in
the [datastores/cases](datastores/cases)
directory, part of the repository.

This directory stores the meta-information related to the `case`, namely: the group, the type, the environment, the patient uuid.
The limited cache is stored in the subdirectory [limited_caches](datastores/cases/limited_caches).

*ATTENTION* The limited cache will be used when running the tests if the `--patient-uuid` is not provided.

The list of the cases can be printed out with:

```shell
uv run python case_list.py
```

When a test is run, its result is saved in the `results` table of the `evaluation_results.db` local SQLite database,
which is *not* part of the repository: it is located in the parent directory of the local repository.

Some statistics about the results can be displayed by running:

```shell
uv run python case_statistics.py
```

To store the results in a PostGreSQL database, add to the environment the variables:

```shell
export EVALUATIONS_DB_NAME="..."
export EVALUATIONS_DB_USERNAME="..."
export EVALUATIONS_DB_PASSWORD="..."
export EVALUATIONS_DB_HOST="..."
export EVALUATIONS_DB_PORT=000
```

The table `results` should already exist in the database and defined as:

```postgresql
CREATE TABLE IF NOT EXISTS "results"
(
    "id"            SERIAL PRIMARY KEY,
    "created"       TIMESTAMP NOT NULL,
    "run_uuid"      TEXT      NOT NULL,
    "plugin_commit" TEXT      NOT NULL,
    "case_type"     TEXT      NOT NULL,
    "case_group"    TEXT      NOT NULL,
    "case_name"     TEXT      NOT NULL,
    "test_name"     TEXT      NOT NULL,
    "milliseconds"  REAL      NOT NULL,
    "passed"        BOOLEAN   NOT NULL,
    "errors"        TEXT      NOT NULL
);
```

#### Display a summary of the cases

When creating the cases based on audio files or a transcript, the option `--render` will generate the commands to see them in the UI. 

The following command will display in the system's default browser a summary of the detected instructions and the generated commands:

```shell
uv  run python case_builder.py --case the_case --summarize
```

### Delete evaluation tests

A set of evaluation tests (or `case`) can be deleted using:

```shell
# remove all files related to the case
uv  run python case_builder.py --case the_case --delete --audios

# remove all files related to the case, except the files of the `audios` folder and the `audio2transcript.json` file.
uv  run python case_builder.py --case the_case --delete
```

The files related to the `case` in the directory [datastores/cases](datastores/cases) will be removed.
