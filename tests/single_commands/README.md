The shell script [run_single_command_chart.sh](run_single_command_chart.sh) runs sequentially the
script [builder_from_chart_transcript.py](../../evaluations/case_builders/builder_from_chart_transcript.py)
on all the [transcripts files](transcripts) using the [prepared limit cache](limited_caches/for_single_command.json)

The script allows to check _quickly_ the command generation.

The shell script [run_single_command_patient.sh](run_single_command_patient.sh) runs sequentially the
script [builder_from_chart_transcript.py](../../evaluations/case_builders/builder_from_transcript.py)
on all the [transcripts files](transcripts) targeting the existing patient provided as argument (e.g.
`./run_single_command_patient.sh a000000000000001000000000000001a`)

The script allows to check _quickly_ the command generation and the creation of the command in the UI.



The scripts assume running in an environment with all the necessary variables correct set up.
This includes:
```shell
export IS_SCRIPT=0
export ONTOLOGIES_ENDPOINT="..."
export SCIENCE_ENDPOINT="..."
export PRE_SHARED_KEY="..."
#
export CANVAS_SDK_DB_NAME="..."
export CANVAS_SDK_DB_USERNAME="..."
export CANVAS_SDK_DB_PASSWORD="..."
export CANVAS_SDK_DB_HOST="..."
export CANVAS_SDK_DB_PORT=000

export EVALUATIONS_DB_NAME="..."
export EVALUATIONS_DB_USERNAME="..."
export EVALUATIONS_DB_PASSWORD="..."
export EVALUATIONS_DB_HOST="..."
export EVALUATIONS_DB_PORT=000

export VendorAudioLLM="OpenAI/Google/ElevenLabs/..."
export KeyAudioLLM="..."
export VendorTextLLM="OpenAI/Google/..."
export KeyTextLLM="...."

export CUSTOMER_IDENTIFIER="local"
export APISigningKey="..."

# and optionally:
export AwsKey="..."
export AwsSecret="..."
export AwsRegion="..."
export AwsBucketLogs="..."
# OR
export S3CredentialsLogs='{"key":"...","secret":"...","region":"...","bucket":"..."}'

export MaxWorkers=1
export StructuredReasonForVisit="n"
export AuditLLMDecisions="n"

export CommandsPolicy="n"
export CommandsList=""
export StaffersPolicy="y"
export StaffersList=""
export CycleTranscriptOverlap="75"


```