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

* a tests suite run with `pytest` that checks step by step the coherence and the value of the plugin
* a cases suite run with [`case_runner.py`](../case_runner.py) script that executes an end to end scenario and evaluate it against a rubric

The `pytest` approach is designed to help understand and improve the plugin deep and narrowly.

The rubric approach is designed to offer an overall quality benchmark of the plugin. Currently, the [`case_runner.py`](../case_runner.py) script
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


The _cases_ evaluations are in a folder `cases/theCaseName`, one JSON file per step for all cycles, except the audio files, stored in a `audios` subfolder.

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

The case builders are scripts that create all evaluation tests from end to end.

The evaluation tests are stored in the [cases](cases) directory, one subdirectory per case.

These evaluations of a case are run all at once with:

```shell
uv run pytest -v --end2end evaluations/test_end2end.py::test_end2end[the_case]
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
- the `summary.html` file, HTML file to display the summarized commands _based_ on the `summary_revised.json` file ; it can be updated with the command `uv run python case_builder.py --case the_case --summarize`

Note that when removing the case files with the command `uv run python case_builder.py --case the_case --delete [--audios]`, the files `summary.html` and `summary_revised.json` are not removed.

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
uv  run pytest -v --end2end evaluations/test_end2end.py::test_end2end[the_case]
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

Based on a `json` file, transcript of the conversation, a set (i.e., covering all steps except the first one) of evaluation tests can be created using:

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

When creating a `case` by running the [`case_builder.py`](../case_builder.py) script, a file is created/updated in
the [datastores/cases](datastores/cases) directory, part of the repository.

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
  "cycles"        INT       NOT NULL,
  "test_name"     TEXT      NOT NULL,
  "cycle"         INT       NOT NULL,
  "milliseconds"  REAL      NOT NULL,
  "passed"        BOOLEAN   NOT NULL,
  "errors"        TEXT      NOT NULL
);
```

#### Display a summary of the cases

When creating the cases based on audio files or a transcript, the option `--render` will generate the commands to see them in the UI. 

The following command will display in the system's default browser a summary of the detected instructions and the generated commands, based on the `summary_revised.json`:

```shell
uv  run python case_builder.py --case the_case --summarize
```

### Delete evaluation tests

A set of evaluation tests (or `case`) can be deleted using:

```shell
# remove all files related to the case, except the summary_revised.json and summary.html
uv  run python case_builder.py --case the_case --delete --audios

# remove files as above, except the files of the `audios` folder and the `audio2transcript.json` file.
uv  run python case_builder.py --case the_case --delete
```

The files related to the `case` in the directory [datastores/cases](datastores/cases) will be removed.
