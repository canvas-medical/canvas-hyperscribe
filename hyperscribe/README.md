hyperscribe
===========

Plugin inserting commands based on the content of an audio, discussion between a patient and a provider.

## Components

The plugin provides these components:

- [launcher](handlers/capture_button.py): button in the header of the note (UI) to start the recording
- [reviewer](handlers/reviewer_button.py): button in the header of the note (UI) to review the LLM decisions
- [tuning_launcher](handlers/tuning_launcher.py): button in the header of the note (UI) to start the recording for tuning purpose

## Set up

In your home directory, add to `~/.canvas/credentials.ini` the host you have access to:

```shell
[my-canvas-host]
client_id=...
client_secret=...
```

(as described in the [Canvas Plugin Overview](https://www.youtube.com/watch?v=X2JOEElq2ck) video)

To be able to locally run your code against your remote instance (`my-canvas-host.canvasmedical.com`), create the environment variables:

```shell
export IS_SCRIPT=0 # or provide the database access through CANVAS_SDK_DB_URL
export CANVAS_SDK_DB_NAME="..."
export CANVAS_SDK_DB_USERNAME="..."
export CANVAS_SDK_DB_PASSWORD="..."
export CANVAS_SDK_DB_HOST="..."
export CANVAS_SDK_DB_PORT=000
```

## Useful commands

Install the plugin or re-install it while keeping the secrets

```shell
canvas install --host my-canvas-host hyperscribe 
```

Disable an installed plugin, while keeping the secrets

```shell
canvas disable --host my-canvas-host hyperscribe 
```

Uninstall an installed plugin, and remove its secrets

```shell
canvas uninstall --host my-canvas-host hyperscribe 
```

Tail the logs of the remote canvas instance

```shell
canvas logs --host my-canvas-host 
```

## Plugin _secrets_

The `secrets` are stored in the Canvas instance database and can be upsert in `https://my-canvas-host.canvasmedical.com/admin/plugin_io/plugin/`.

| Secret                           | Values                                      | Comments                                                                                                                                                    |
|----------------------------------|---------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `APISigningKey`                  |                                             | generated key to accept published effects from the case builder                                                                                             |
| `AudioHost`                      |                                             | `audio` Canvas service                                                                                                                                      |
| `AudioIntervalSeconds`           | `20`                                        | duration of each audio chunk                                                                                                                                |
| `AuditLLMDecisions`              | `y`, `yes` or `1`                           | any other value means `no`/`false`                                                                                                                          |
| `AwsBucketLogs`                  |                                             | AWS bucket of the S3 service for the logs                                                                                                                   |
| `AwsBucketTuning`                |                                             | AWS bucket of the S3 service for the tuning files                                                                                                           |
| `AwsKey`                         |                                             | AWS key to access the S3 service                                                                                                                            |
| `AwsRegion`                      |                                             | AWS region of the S3 service                                                                                                                                |
| `AwsSecret`                      |                                             | AWS secret to access the S3 service                                                                                                                         |
| `CommandsList`                   | `Command1,Command2 Command3`                | list of commands, as defined in [libraries/implemented_commands.py::command_list](libraries/implemented_commands.py), related to the `CommandsPolicy` value |
| `CommandsPolicy`                 | `y`, `yes` or `1`                           | the commands of `CommandsList` are allowed (`y`) or excluded (`n`)                                                                                          |
| `CustomPrompts`                  | `[{"command":"...", "prompt": "..."}, ...]` | list of custom prompts for the commands `FollowUp`, `HistoryOfPresentIllness`, `Instruct`, `Plan`, `ReasonForVisit`.                                        |
| `CycleTranscriptOverlap`         | `100`                                       | the numbers of words from the end of the last audio chunk provided to the LLM when generating the transcript from the audio                                 |
| `HierarchicalDetectionThreshold` | `5`                                         | the minimum numbers of staged common commands to use the hierarchical instruction detection flow (opposed to the flat instruction detection)                |
| `IsTuning`                       | `y`, `yes` or `1`                           | any other value means `no`/`false`, if `true`, only the `Tuning` button is displayed, otherwise the `Hyperscribe` and `Reviewer` buttons are displayed      |
| `MaxWorkers`                     |                                             | the number of concurrent commands computed                                                                                                                  |
| `StaffersList`                   | `key1 key2, key3`                           | list of staffer keys, related to the `StaffersPolicy` value                                                                                                 |
| `StaffersPolicy`                 | `y`, `yes` or `1`                           | the staffers of `StaffersList` are allowed (`y`) or excluded (`n`)                                                                                          |
| `StructuredReasonForVisit`       | `y`, `yes` or `1`                           | any other value means `no`/`false`                                                                                                                          |
| `TrialStaffersList`              | `key1 key2, key3`                           | list of trial staffer keys allowed to use hyperscribe on test patients whose name matches the pattern Hyperscribe* ZZTest*                                  |
| `VendorAudioLLM`                 | `OpenAi`, `Google`                          | by default `OpenAi` (case insensitive)                                                                                                                      |
| `KeyAudioLLM`                    |                                             | the vendor's API key                                                                                                                                        |
| `VendorTextLLM`                  | `OpenAi`, `Google`, `Anthropic`             | by default `OpenAi` (case insensitive)                                                                                                                      |
| `KeyTextLLM`                     |                                             | the vendor's API key                                                                                                                                        |


The logs, mainly the communication with the LLMs, are stored in a `AWS S3 bucket` if credentials are provided as listed above. The credentials must belong to an AWS IAM user with username following the format `hyperscribe-{canvas_instance}`.

The `AuditLLMDecisions` secret directs the LLM to provide, or not, the rationale used at each step, giving a better understanding of the command
generation. When set, the audit is generated at the end of the session, and it can be viewed through the `Reviewer` button.

The audits are saved in the provided `AWS S3 bucket`.

The logs are saved following the folder structure:

```shell
AwsBucket
      |- hyperscribe-{canvas_instance}
           |- audits - all audit files
           |- finals - concatenated logs of each cycle
           |- llm_turns - log of each LLM communication
           |- partials - logs of each step
```

## Unit tests

The `hyperscribe` code is tested with `pytest` and discussed in this [README.md](../README.md)
