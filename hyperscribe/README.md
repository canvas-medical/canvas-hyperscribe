hyperscribe
===========

Plugin inserting commands based on the content of an audio, discussion between a patient and a provider.

## Components

The plugin provides these components:

- [launcher](handlers/launcher.py): button in the header of the note (UI) to start the recording
- [commander](handlers/commander.py): script executed on the server creating the commands based on the audio
- [reviewer](handlers/reviewer_button.py): button in the header of the note (UI) to review the LLM decisions

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
| `AuditLLMDecisions`        | `y`, `yes` or `1`               | any other value means `no`/`false`            |
| `AwsKey`                   |                                 | AWS key to access the S3 service              |
| `AwsSecret`                |                                 | AWS secret to access the S3 service           |
| `AwsRegion`                |                                 | AWS region of the S3 service                  |
| `AwsBucket`                |                                 | AWS bucket of the S3 service                  |

To use the Canvas services provided by the SDK (`OntologiesHttp` and `ScienceHttp` from `canvas_sdk.utils.http`), set to empty the related secrets (
`OntologiesHost` and `ScienceHost`).

The logs, mainly the communication with the LLMs, are stored in a `AWS S3 bucket` if credentials are provided as listed above.

The `AuditLLMDecisions` secret directs the LLM to provide, or not, the rationale used at each step, giving a better understanding of the command
generation. When set, the audit is generated at the end of the session, and it can be viewed through the `Reviewer` button.

The audits are saved in the provided `AWS S3 bucket`.

The logs are saved following the folders structure:

```shell
AwsBucket
      |- canvas-instance
           |- audits - all audit files
           |- finals - concatenated logs of each cycle
           |- llm_turns - log of each LLM communication
           |- partials - logs of each step
```

### Temporary set up

The _Perform_ command needs `CPT` codes provided through the model [`ChargeDescriptionMaster`](./handlers/temporary_data.py).

The underlying view is not exposed to the SDK yet (see [issue #463](https://github.com/canvas-medical/canvas-plugins/issues/463)), and it can be
created with the following SQL script run on the CANVAS instance:

```postgresql
CREATE OR REPLACE VIEW canvas_sdk_data_charge_description_master_001 AS
SELECT id, cpt_code, name, short_name
FROM quality_and_revenue_chargedescriptionmaster;

GRANT SELECT ON canvas_sdk_data_charge_description_master_001 TO canvas_sdk_read_only;
```

## Unit tests

The `hyperscribe` code is tested with `pytest` and discussed in this [README.md](../README.md)
