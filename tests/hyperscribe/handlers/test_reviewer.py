from datetime import timezone, datetime
from unittest.mock import patch, call

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.events.base import TargetType
from canvas_sdk.v1.data import Note, Patient, Staff

from hyperscribe.handlers.reviewer import Reviewer
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.aws_s3_object import AwsS3Object
from tests.helper import is_constant


def test_constants():
    tested = Reviewer
    constants = {
        "BUTTON_TITLE": "📖 Reviewer",
        "BUTTON_KEY": "HYPERSCRIBE_REVIEWER",
        "BUTTON_LOCATION": "note_header",
        "RESPONDS_TO": ["SHOW_NOTE_HEADER_BUTTON", "ACTION_BUTTON_CLICKED"],
        "PRIORITY": 0,
    }
    assert is_constant(tested, constants)


@patch.object(Note, "objects")
@patch('hyperscribe.handlers.reviewer.render_to_string')
@patch('hyperscribe.handlers.reviewer.AwsS3')
@patch('hyperscribe.handlers.reviewer.LaunchModalEffect')
def test_handle(launch_model_effect, aws_s3, render_to_string, note_db):
    def reset_mocks():
        launch_model_effect.reset_mock()
        aws_s3.reset_mock()
        render_to_string.reset_mock()
        note_db.reset_mock()

    aws_s3_credentials = AwsS3Credentials(
        aws_key='theKey',
        aws_secret='theSecret',
        region='theRegion',
        bucket='theBucket',
    )
    a_date = datetime(2025, 5, 8, 7, 11, 45, tzinfo=timezone.utc)

    event = Event(EventRequest(context='{"note_id":"noteId"}'))
    event.target = TargetType(id="targetId", type=Patient)
    secrets = {
        "AwsKey": "theKey",
        "AwsSecret": "theSecret",
        "AwsRegion": "theRegion",
        "AwsBucket": "theBucket",
    }
    environment = {
        "CUSTOMER_IDENTIFIER": "theTestEnv",
    }
    tested = Reviewer(event, secrets, environment)

    # s3 not ready
    launch_model_effect.return_value.apply.side_effect = [Effect(type="LOG", payload="SomePayload")]
    launch_model_effect.TargetType.DEFAULT_MODAL = "default_modal"
    note_db.get.side_effect = [Note(
        id="uuidNote",
        patient=Patient(id="uuidPatient"),
        provider=Staff(id="uuidProvider"),
    )]
    aws_s3.return_value.is_ready.side_effect = [False]
    aws_s3.return_value.list_s3_objects.side_effect = []
    aws_s3.return_value.generate_presigned_url.side_effect = []
    render_to_string.side_effect = ["theRenderedString"]

    result = tested.handle()
    expected = [Effect(type="LOG", payload="SomePayload")]
    assert result == expected

    calls = [
        call(content="theRenderedString", target='default_modal'),
        call().apply(),
    ]
    assert launch_model_effect.mock_calls == calls
    calls = [call.get(dbid='noteId')]
    assert note_db.mock_calls == calls
    calls = [
        call(aws_s3_credentials),
        call().is_ready(),
    ]
    assert aws_s3.mock_calls == calls
    calls = [call("handlers/reviewer.html", {"url_list": "[]"})]
    assert render_to_string.mock_calls == calls
    reset_mocks()

    # s3 is ready
    launch_model_effect.return_value.apply.side_effect = [Effect(type="LOG", payload="SomePayload")]
    launch_model_effect.TargetType.DEFAULT_MODAL = "default_modal"
    note_db.get.side_effect = [Note(
        id="uuidNote",
        patient=Patient(id="uuidPatient"),
        provider=Staff(id="uuidProvider"),
    )]
    aws_s3.return_value.is_ready.side_effect = [True]
    aws_s3.return_value.list_s3_objects.side_effect = [
        [
            AwsS3Object(key="path01", last_modified=a_date, size=4785236),
            AwsS3Object(key="path02", last_modified=a_date, size=4785236),
            AwsS3Object(key="path03", last_modified=a_date, size=4785236),
        ],
    ]
    aws_s3.return_value.generate_presigned_url.side_effect = [
        "pre_assigned_01",
        "pre_assigned_02",
        "pre_assigned_03",
    ]
    render_to_string.side_effect = ["theRenderedString"]

    result = tested.handle()
    expected = [Effect(type="LOG", payload="SomePayload")]
    assert result == expected

    calls = [
        call(content="theRenderedString", target='default_modal'),
        call().apply(),
    ]
    assert launch_model_effect.mock_calls == calls
    calls = [call.get(dbid='noteId')]
    assert note_db.mock_calls == calls
    calls = [
        call(aws_s3_credentials),
        call().is_ready(),
        call().list_s3_objects('theTestEnv/audits/uuidNote/'),
        call().generate_presigned_url('path01', 1200),
        call().generate_presigned_url('path02', 1200),
        call().generate_presigned_url('path03', 1200),
    ]
    assert aws_s3.mock_calls == calls
    calls = [call(
        "handlers/reviewer.html",
        {"url_list": '["pre_assigned_01", "pre_assigned_02", "pre_assigned_03"]'},
    )]
    assert render_to_string.mock_calls == calls
    reset_mocks()


def test_visible():
    event = Event(EventRequest())
    tests = [
        ("yes", True),
        ("no", False),
    ]
    for audit_llm, expected in tests:
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
            "AuditLLMDecisions": audit_llm,
            "AwsKey": "theKey",
            "AwsSecret": "theSecret",
            "AwsRegion": "theRegion",
            "AwsBucket": "theBucket",
        }
        tested = Reviewer(event, secrets)
        assert tested.visible() is expected
