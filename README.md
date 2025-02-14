# commander_audio_plugin

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

The Canvas plugin itself is in the folder `commander`.

Useful commands:
```shell
canvas install --host my-canvas-host commander # install the plugin or re-install it while keeping the secrets 
canvas disable --host my-canvas-host commander # disable an installed plugin, while keeping the secrets
canvas uninstall --host my-canvas-host commander # uninstall an installed plugin, as well as its secrets

canvas logs --host my-canvas-host # tail the logs of the remote canvas instance
```

The `secrets` are stored in the Canvas instance database and can be upsert in `https://my-canvas-host.canvasmedical.com/admin/plugin_io/plugin/`.

## Unit tests

The `commander` code is tested with `pytest`.
```shell
poetry run pytest -vv tests/ # run all tests and fully display any failure 

poetry run pytest tests/ --cov=. # run all tests and report the coverage
```

## Integration tests

The `commander` plugin has four essential steps:
1. transcript the audio into a discussion, identifying the speakers and what they say
1. extract from the discussion a set of instructions, a plain english description of a Canvas command
1. transform an instruction into a data structure close to a Canvas command parameters
1. create the Canvas command based on the parameters

The integration tests are designed to test each of these steps.

The convention used is to have:
- a folder where to store tests for each step (`integrations/audio2transcript`, `integrations/transcript2instruction`...)
- a test file to run the stored tests of each step (`test_audio2transcript.py`, `test_transcript2instructions.py`...)

The tests are JSON files with the input and the expected output for the considered step. 

### Run integration tests

The integration tests are run as `pytest` tests.

The basic idea is that all figures or dates should be exactly the same from one run to another one.
It is possible to ignore the value of a key when comparing the expected output and the actual output by setting it to `>?<` (see [here](integrations/helper_settings.py) the method `json_nuanced_differences`).

The following parameters can be used to configure the integration test:
- `--integration-difference-levels` – Specifies the expected level of accuracy for any text value (`minor`, `moderate`, `severe`, `critical` as defined [here](integrations/helper_settings.py) as `DIFFERENCE_LEVELS`).
- `--patient-uuid` – Identifies the patient to run the integration test against, it is __mandatory__ for most tests.

Among standard `pytest` parameters, `-k` is useful as it allows to target a specific test.

```shell
# run all integration tests for the patient patient_uuid
poetry run pytest -v integrations --patient-uuid patient_uuid

# run the test the_name defined for the step audio2transcript, accepting all differences minor, moderate and severe
poetry run pytest -v integrations/test_audio2transcript.py -k the_name --integration-difference-levels "minor,moderate,severe"

# run the test the_name defined for the step instruction2parameters for the patient patient_uuid
poetry run pytest -v integrations/test_instruction2parameters.py -k the_name --patient-uuid patient_uuid

# run all tests for the step parameters2command for the patient patient_uuid
poetry run pytest -v integrations/test_parameters2command.py --patient-uuid patient_uuid

# run all tests for the step transcript2instructions for the patient patient_uuid
poetry run pytest -v integrations/test_transcript2instructions.py --patient-uuid patient_uuid
```

### Create integration tests

Based on a set of `mp3` files, an integration test can be created using:
```shell
poetry run python case_builder.py \
  --patient patient_uuid \
  --label the_name \
  --mp3 "file/path/to/file_01.mp3" "file/path/to/file_02.mp3"
```

### Delete integration tests

An integration test can be deleted using:
```shell
poetry run python case_builder.py --label the_name --delete
```
