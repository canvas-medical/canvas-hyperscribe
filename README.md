# Hyperscribe

Plugin inserting commands based on the content of an audio, discussion between a patient and a provider.

## Set up

In your home directory, add to `~/.canvas/credentials.ini` the host you have access to:

```shell
[my-canvas-host]
client_id=...
client_secret=...
```

(as described in the [Canvas Plugin Overview](https://www.youtube.com/watch?v=X2JOEElq2ck) video)

To be able to run locally your code against your remote instance (`my-canvas-host.canvasmedical.com`), create the environment variables:

```shell
export CANVAS_SDK_DB_NAME="..."
export CANVAS_SDK_DB_USERNAME="..."
export CANVAS_SDK_DB_PASSWORD="..."
export CANVAS_SDK_DB_HOST="..."
export CANVAS_SDK_DB_PORT=000
```

## Canvas plugin

The Canvas plugin itself is in the folder `hyperscribe`.

Useful commands:

```shell
# install the plugin or re-install it while keeping the secrets
canvas install --host my-canvas-host hyperscribe 

# disable an installed plugin, while keeping the secrets 
canvas disable --host my-canvas-host hyperscribe 

# uninstall an installed plugin, and remove its secrets
canvas uninstall --host my-canvas-host hyperscribe 

# tail the logs of the remote canvas instance
canvas logs --host my-canvas-host 
```

The `secrets` are stored in the Canvas instance database and can be upsert in `https://my-canvas-host.canvasmedical.com/admin/plugin_io/plugin/`.

| Secret                     | Values                          | Comments                                      |
|----------------------------|---------------------------------|-----------------------------------------------|
| `AudioHost`                |                                 | `audio` Canvas service                        |
| `AudioIntervalSeconds`     | `20`                            | duration of each audio chunk                  |
| `VendorTextLLM`            | `OpenAi`, `Google`, `Anthropic` | by default `OpenAi` (case insensitive)        |
| `KeyTextLLM`               |                                 | the vendor's API key                          |
| `VendorAudioLLM`           | `OpenAi`, `Google`              | by default `OpenAi` (case insensitive)        |
| `KeyAudioLLM`              |                                 | the vendor's API key                          |
| `ScienceHost`              |                                 | `science` Canvas service                      |
| `OntologiesHost`           |                                 | `ontologies` Canvas service                   |
| `PreSharedKey`             |                                 | key provided by Canvas to access `ontologies` |
| `StructuredReasonForVisit` | `y`, `yes` or `1`               | any other value means `no`/`false`            |
| `AwsKey`                   |                                 | AWS key to access the S3 service              |
| `AwsSecret`                |                                 | AWS secret to access the S3 service           |
| `AwsRegion`                |                                 | AWS region of the S3 service                  |
| `AwsBucket`                |                                 | AWS bucket of the S3 service                  |

The logs, mainly the communication with the LLMs, are stored in a `AWS S3 bucket` if credentials are provided as listed above. 

## Unit tests

The `hyperscribe` code is tested with `pytest`.

```shell
uv  run pytest -vv tests/ # run all tests and fully display any failure 

uv  run pytest tests/ --cov=. # run all tests and report the coverage
```

## Evaluation tests

The `hyperscribe` plugin has four essential steps:

1. transcript the audio into a discussion, identifying the speakers and what they say
1. extract from the discussion a set of instructions, a plain english description of a Canvas command
1. transform an instruction into a data structure close to a Canvas command parameters
1. create the Canvas command based on the parameters

The evaluation tests are designed to test each of these steps.

The convention used is to have:

- a folder where to store tests for each step (`evaluations/audio2transcript`, `evaluations/transcript2instruction`...)
- a test file to run the stored tests of each step (`test_audio2transcript.py`, `test_transcript2instructions.py`...)

The tests are JSON files with the input and the expected output for the considered step.

### Run evaluation tests

The evaluation tests are run as `pytest` tests.

The basic idea is that all figures or dates should be exactly the same from one run to another one.
It is possible to ignore the value of a key when comparing the expected output and the actual output by setting it to `>?<` (
see [here](evaluations/helper_settings.py) the method `json_nuanced_differences`).

The following parameters can be used to configure the evaluation test:

- `--evaluation-difference-levels` – Specifies the expected level of accuracy for any text value (`minor`, `moderate`, `severe`, `critical` as
  defined [here](evaluations/helper_settings.py) as `DIFFERENCE_LEVELS`).
- `--patient-uuid` – Identifies the patient to run the evaluation test against, it is __mandatory__ for most tests.

Among standard `pytest` parameters, `-k` is useful as it allows to target a specific test.

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

# run all steps for a specific case the_case
# for the patient patient_uuid
uv  run pytest -v evaluations  -k the_case --patient-uuid patient_uuid
```

### Create evaluation tests

To be able to create evaluation codes locally, in addition to the `CANVAS_SDK_DB_...` defined above, create the environment variables:

```shell
export VendorTextLLM="OpenAI"
export KeyTextLLM="..."
export VendorAudioLLM="Google"
export KeyAudioLLM="..."
export ScienceHost="..."
export OntologiesHost="...."
export PreSharedKey="...."
export StructuredReasonForVisit="y" or "n"
```
The logs will be sent to the `AWS S3 bucket` if the following environment variables are set:

```shell
export AwsKey="..."
export AwsSecret="..."
export AwsRegion="..."
export AwsBucket="..."
```

Based on a set of `mp3` files, a set (i.e. covering all steps) of evaluation tests can be created using:

```shell
uv  run python case_builder.py \
  --patient patient_uuid \
  --label the_case \
  --mp3 "file/path/to/file_01.mp3" \
  "file/path/to/file_02.mp3" \
  "file/path/to/file_03.mp3"
```

Note that on the first step (`audio2transcript`):

- all `mp3` files are saved in the `evaluations/audio2transcript/inputs_mp3/` folder, the first one using the `--label` as name, the subsequent files
  have the same name with an added number,

On the second step (`transcript2instructions`):

- the `uuid` of the instructions is by default set empty
- the order of the instructions of different type is ignored

### Delete evaluation tests

A set of evaluation tests can be deleted using:

```shell
uv  run python case_builder.py --label the_case --delete
```
