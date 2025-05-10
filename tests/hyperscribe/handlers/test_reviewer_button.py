from time import time
from unittest.mock import patch, call

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.events.base import TargetType
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.v1.data import Note, Patient, Staff

from hyperscribe.handlers.reviewer_button import ReviewerButton
from tests.helper import is_constant


def test_class():
    tested = ReviewerButton
    assert issubclass(tested, ActionButton)


def test_constants():
    tested = ReviewerButton
    constants = {
        "BUTTON_TITLE": "📖 Reviewer",
        "BUTTON_KEY": "HYPERSCRIBE_REVIEWER",
        "BUTTON_LOCATION": "note_header",
        "RESPONDS_TO": ["SHOW_NOTE_HEADER_BUTTON", "ACTION_BUTTON_CLICKED"],
        "PRIORITY": 0,
    }
    assert is_constant(tested, constants)


@patch("hyperscribe.handlers.reviewer_button.time", wraps=time)
@patch.object(Note, "objects")
@patch('hyperscribe.handlers.reviewer_button.LaunchModalEffect')
def test_handle(launch_model_effect, note_db, mock_time):
    def reset_mocks():
        launch_model_effect.reset_mock()
        note_db.reset_mock()
        mock_time.reset_mock()

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
    tested = ReviewerButton(event, secrets, environment)

    mock_time.side_effect = [1746790419.775192]
    launch_model_effect.return_value.apply.side_effect = [Effect(type="LOG", payload="SomePayload")]
    launch_model_effect.TargetType.NEW_WINDOW = "new_window"
    note_db.get.side_effect = [Note(
        id="uuidNote",
        patient=Patient(id="uuidPatient"),
        provider=Staff(id="uuidProvider"),
    )]

    result = tested.handle()
    expected = [Effect(type="LOG", payload="SomePayload")]
    assert result == expected

    calls = [call()]
    assert mock_time.mock_calls == calls
    calls = [
        call(
            url='/plugin-io/api/hyperscribe/reviewer?'
                'note_id=uuidNote&'
                'patient_id=uuidPatient&'
                'ts=1746790419&'
                'sig=db6ba533682736ca1937979afa2b461c49f659f73cc565e64e00771c77e8d5be',
            target='new_window',
        ),
        call().apply(),
    ]
    assert launch_model_effect.mock_calls == calls
    calls = [call.get(dbid='noteId')]
    assert note_db.mock_calls == calls

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
        tested = ReviewerButton(event, secrets)
        assert tested.visible() is expected


@patch("hyperscribe.handlers.reviewer_button.time", wraps=time)
def test_presigned_url(mock_time):
    def reset_mocks():
        mock_time.reset_mock()

    tested = ReviewerButton

    mock_time.side_effect = [1746790419.775192]

    result = tested.presigned_url("thePatientUuid", "theNoteUuid", "theSecret")
    expected = ("/plugin-io/api/hyperscribe/reviewer?"
                "note_id=theNoteUuid&"
                "patient_id=thePatientUuid&"
                "ts=1746790419&"
                "sig=db6ba533682736ca1937979afa2b461c49f659f73cc565e64e00771c77e8d5be")
    assert result == expected

    calls = [call()]
    assert mock_time.mock_calls == calls
    reset_mocks()
