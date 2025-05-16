import json
from datetime import datetime, timezone, UTC
from unittest.mock import patch, call, MagicMock

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.v1.data import Command, TaskComment, Note, TaskLabel
from logger import log

from hyperscribe.handlers.reviewer import Reviewer
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey
from tests.helper import is_constant


def test_constants():
    tested = Reviewer
    constants = {
        "RESPONDS_TO": ["TASK_COMMENT_CREATED"],
    }
    assert is_constant(tested, constants)


@patch.object(log, "info")
@patch.object(Note, "objects")
@patch.object(TaskComment, "objects")
@patch.object(Reviewer, "compute_audit_documents")
def test_compute(
        compute_audit_documents,
        task_comment_db,
        note_db,
        info,
):
    mock_comment = MagicMock()
    mock_note = MagicMock()

    def reset_mocks():
        compute_audit_documents.reset_mock()
        task_comment_db.reset_mock()
        note_db.reset_mock()
        info.reset_mock()
        mock_comment.reset_mock()
        mock_note.reset_mock()

    task_labels = [
        TaskLabel(name="label1"),
        TaskLabel(name="label2"),
    ]
    identification = IdentificationParameters(
        patient_uuid='patientUuid',
        note_uuid='noteUuid',
        provider_uuid='providerUuid',
        canvas_instance='theTestEnv',
    )
    secrets = {
        "VendorTextLLM": "theTextVendor",
        "VendorAudioLLM": "theAudioVendor",
        "AwsKey": "theKey",
        "AwsSecret": "theSecret",
        "AwsRegion": "theRegion",
        "AwsBucket": "theBucket",
    }
    event = Event(EventRequest(target="taskUuid"))
    environment = {"CUSTOMER_IDENTIFIER": "theTestEnv"}
    tested = Reviewer(event, secrets, environment)

    # the task comment is not related to the Audio plugin
    compute_audit_documents.side_effect = []
    mock_comment.id = "commentUuid"
    mock_comment.task.id = "taskUuid"
    mock_comment.task.labels.all.side_effect = [task_labels]
    mock_comment.task.labels.filter.return_value.first.side_effect = [""]
    task_comment_db.get.side_effect = [mock_comment]

    result = tested.compute()
    assert result == []

    assert compute_audit_documents.mock_calls == []
    calls = [call.get(id='taskUuid')]
    assert task_comment_db.mock_calls == calls
    assert note_db.mock_calls == []
    assert info.mock_calls == []
    calls = [
        call.task.labels.filter(name='Encounter Copilot'),
        call.task.labels.filter().first()
    ]
    assert mock_comment.mock_calls == calls
    assert mock_note.mock_calls == []
    reset_mocks()

    # the task comment is related to the Audio plugin
    # -- the finished date is NOT set
    compute_audit_documents.side_effect = []
    mock_comment.id = "commentUuid"
    mock_comment.body = json.dumps({
        "chunk_index": 7,
        "note_id": "noteUuid",
        "created": "2025-05-09T12:34:55+00:00",
    })
    mock_comment.task.id = "taskUuid"
    mock_comment.task.labels.all.side_effect = [task_labels]
    mock_comment.task.labels.filter.return_value.first.side_effect = ["aTask"]
    task_comment_db.get.side_effect = [mock_comment]

    result = tested.compute()
    assert result == []

    assert compute_audit_documents.mock_calls == []
    calls = [call.get(id='taskUuid')]
    assert task_comment_db.mock_calls == calls
    assert note_db.mock_calls == []
    assert info.mock_calls == []
    calls = [
        call.task.labels.filter(name='Encounter Copilot'),
        call.task.labels.filter().first()
    ]
    assert mock_comment.mock_calls == calls
    assert mock_note.mock_calls == []
    reset_mocks()
    # -- the finished date is set
    compute_audit_documents.side_effect = [(True, [Effect(type="LOG", payload="SomePayload")])]
    mock_comment.id = "commentUuid"
    mock_comment.body = json.dumps({
        "chunk_index": 7,
        "note_id": "noteUuid",
        "created": "2025-05-09T12:34:55+00:00",
        "finished": "2025-05-09T12:41:17+00:00",
    })
    mock_comment.task.id = "taskUuid"
    mock_comment.task.labels.all.side_effect = [task_labels]
    mock_comment.task.labels.filter.return_value.first.side_effect = ["aTask"]
    task_comment_db.get.side_effect = [mock_comment]
    mock_note.provider.id = "providerUuid"
    mock_note.patient.id = "patientUuid"
    note_db.get.side_effect = [mock_note]

    result = tested.compute()
    assert result == []
    calls = [call(identification, datetime(2025, 5, 9, 12, 34, 55, tzinfo=UTC), 7)]
    assert compute_audit_documents.mock_calls == calls
    calls = [call.get(id='taskUuid')]
    assert task_comment_db.mock_calls == calls
    calls = [call.get(id='noteUuid')]
    assert note_db.mock_calls == calls
    calls = [call('  => create the final audit')]
    assert info.mock_calls == calls
    calls = [
        call.task.labels.filter(name='Encounter Copilot'),
        call.task.labels.filter().first()
    ]
    assert mock_comment.mock_calls == calls
    assert mock_note.mock_calls == []
    reset_mocks()


@patch('hyperscribe.handlers.reviewer.LlmDecisionsReviewer')
@patch('hyperscribe.handlers.reviewer.Progress')
@patch.object(Command, "objects")
@patch.object(ImplementedCommands, 'schema_key2instruction')
def test_compute_audit_documents(
        schema_key2instruction,
        command_db,
        progress,
        llm_decisions_reviewer,
):
    def reset_mocks():
        schema_key2instruction.reset_mock()
        command_db.reset_mock()
        progress.reset_mock()
        llm_decisions_reviewer.reset_mock()

    secrets = {
        "AudioHost": "theAudioHost",
        "KeyTextLLM": "theKeyTextLLM",
        "VendorTextLLM": "theVendorTextLLM",
        "KeyAudioLLM": "theKeyAudioLLM",
        "VendorAudioLLM": "theVendorAudioLLM",
        "ScienceHost": "theScienceHost",
        "OntologiesHost": "theOntologiesHost",
        "PreSharedKey": "thePreSharedKey",
        "StructuredReasonForVisit": "yes",
        "AuditLLMDecisions": "yes",
        "AwsKey": "theKey",
        "AwsSecret": "theSecret",
        "AwsRegion": "theRegion",
        "AwsBucket": "theBucket",
        "APISigningKey": "theApiSigningKey",
    }
    event = Event(EventRequest(target="taskUuid"))
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    aws_s3_credentials = AwsS3Credentials(
        aws_key='theKey',
        aws_secret='theSecret',
        region='theRegion',
        bucket='theBucket',
    )
    settings = Settings(
        llm_text=VendorKey(vendor="theVendorTextLLM", api_key="theKeyTextLLM"),
        llm_audio=VendorKey(vendor="theVendorAudioLLM", api_key="theKeyAudioLLM"),
        science_host='theScienceHost',
        ontologies_host='theOntologiesHost',
        pre_shared_key='thePreSharedKey',
        structured_rfv=True,
        audit_llm=True,
        api_signing_key="theApiSigningKey",
        send_progress=True,
    )
    date_x = datetime(2025, 5, 9, 12, 29, 21, tzinfo=timezone.utc)
    schema_key2instruction.side_effect = [
        {
            "canvasCommandX": "theInstructionX",
            "canvasCommandY": "theInstructionY",
            "canvasCommandZ": "theInstructionZ",
            "Questionnaire": "Questionnaire",
        },
    ]
    command_db.filter.return_value.order_by.side_effect = [
        [
            Command(schema_key="canvasCommandX", id="uuid1"),
            Command(schema_key="canvasCommandY", id="uuid2"),
            Command(schema_key="canvasCommandY", id="uuid3"),
            Command(schema_key="Questionnaire", id="uuid4"),
        ],
    ]

    tested = Reviewer(event, secrets)
    tested.compute_audit_documents(identification, date_x, 4)

    calls = [call()]
    assert schema_key2instruction.mock_calls == calls
    calls = [call.send_to_user(identification, settings, "EOF")]
    assert progress.mock_calls == calls
    calls = [call.review(
        identification,
        settings,
        aws_s3_credentials,
        {
            'theInstructionX_00': 'uuid1',
            'theInstructionY_01': 'uuid2',
            'theInstructionY_02': 'uuid3',
            'Questionnaire_03': 'uuid4',
        },
        date_x,
        4,
    )]
    assert llm_decisions_reviewer.mock_calls == calls
    reset_mocks()
