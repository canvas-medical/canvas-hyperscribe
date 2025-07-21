import json
from unittest.mock import patch, call

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.events.base import TargetType
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.v1.data.note import Note, CurrentNoteStateEvent
from canvas_sdk.v1.data.patient import Patient
from canvas_sdk.v1.data.staff import Staff

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


@patch.object(Note, "objects")
@patch('hyperscribe.handlers.reviewer_button.Authenticator')
@patch('hyperscribe.handlers.reviewer_button.LaunchModalEffect')
def test_handle(launch_model_effect, authenticator, note_db):
    def reset_mocks():
        launch_model_effect.reset_mock()
        authenticator.reset_mock()
        note_db.reset_mock()

    event = Event(EventRequest(context='{"note_id":"noteId"}'))
    event.target = TargetType(id="targetId", type=Patient)
    secrets = {
        "APISigningKey": "theApiSigningKey",
    }
    environment = {
        "CUSTOMER_IDENTIFIER": "theTestEnv",
    }
    tested = ReviewerButton(event, secrets, environment)

    authenticator.presigned_url.side_effect = ["preSignedUrl"]
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

    calls = [call.presigned_url(
        'theApiSigningKey',
        '/plugin-io/api/hyperscribe/reviewer',
        {'patient_id': 'uuidPatient', 'note_id': 'uuidNote'},
    )]
    assert authenticator.mock_calls == calls
    calls = [
        call(url='preSignedUrl', target='new_window'),
        call().apply(),
    ]
    assert launch_model_effect.mock_calls == calls
    calls = [call.get(dbid='noteId')]
    assert note_db.mock_calls == calls

    reset_mocks()


@patch.object(CurrentNoteStateEvent, "objects")
def test_visible(last_note_state_event_db):
    def reset_mocks():
        last_note_state_event_db.reset_mock()

    tests = [
        ("yes", "yes", "userId", "no", True),
        ("yes", "yes", "otherId", "no", False),
        ("no", "yes", "userId", "no", False),
        ("no", "yes", "otherId", "no", False),
        ("yes", "no", "userId", "no", False),
        ("yes", "no", "otherId", "no", True),
        ("no", "no", "userId", "no", False),
        ("no", "no", "otherId", "no", False),
        #
        ("yes", "yes", "userId", "yes", False),
        ("yes", "no", "otherId", "yes", False),
    ]
    for audit_llm, policy, staff_id, tuning, expected in tests:
        for editable in [True, False]:
            last_note_state_event_db.get.return_value.editable.side_effect = [editable]
            event = Event(EventRequest(context=json.dumps({"note_id": 778, "user": {"id": staff_id}})))
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
                "IsTuning": tuning,
                "AwsKey": "theKey",
                "AwsSecret": "theSecret",
                "AwsRegion": "theRegion",
                "AwsBucketLogs": "theBucketLogs",
                "APISigningKey": "theApiSigningKey",
                "StaffersList": "userId, anotherId",
                "StaffersPolicy": policy,
            }
            tested = ReviewerButton(event, secrets)
            assert tested.visible() is (expected and editable)

            calls = []
            if expected:
                calls = [
                    call.get(note_id=778),
                    call.get().editable(),
                ]
            assert last_note_state_event_db.mock_calls == calls
            reset_mocks()
