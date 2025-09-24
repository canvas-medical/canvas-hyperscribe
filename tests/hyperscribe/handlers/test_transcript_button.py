import json
from unittest.mock import patch, call

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.events.base import TargetType
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.v1.data.note import Note
from canvas_sdk.v1.data.patient import Patient
from canvas_sdk.v1.data.staff import Staff

from hyperscribe.handlers.transcript_button import TranscriptButton
from hyperscribe.libraries.helper import Helper
from tests.helper import is_constant


def test_class():
    tested = TranscriptButton
    assert issubclass(tested, ActionButton)


def test_constants():
    tested = TranscriptButton
    constants = {
        "BUTTON_TITLE": "💬 Transcript",
        "BUTTON_KEY": "HYPERSCRIBE_TRANSCRIPT",
        "BUTTON_LOCATION": "note_header",
        "RESPONDS_TO": ["SHOW_NOTE_HEADER_BUTTON", "ACTION_BUTTON_CLICKED"],
        "PRIORITY": 0,
    }
    assert is_constant(tested, constants)


@patch.object(Note, "objects")
@patch("hyperscribe.handlers.transcript_button.Authenticator")
@patch("hyperscribe.handlers.transcript_button.LaunchModalEffect")
def test_handle(launch_modal_effect, authenticator, note_db):
    def reset_mocks():
        launch_modal_effect.reset_mock()
        authenticator.reset_mock()
        note_db.reset_mock()

    event = Event(EventRequest(context='{"note_id":"noteId"}'))
    event.target = TargetType(id="targetId", type=Patient)
    secrets = {"APISigningKey": "theApiSigningKey"}
    environment = {"CUSTOMER_IDENTIFIER": "theTestEnv"}
    tested = TranscriptButton(event, secrets, environment)

    authenticator.presigned_url.side_effect = ["preSignedUrl"]
    launch_modal_effect.return_value.apply.side_effect = [Effect(type="LOG", payload="SomePayload")]
    launch_modal_effect.TargetType.NEW_WINDOW = "new_window"
    note_db.get.side_effect = [
        Note(id="uuidNote", patient=Patient(id="uuidPatient"), provider=Staff(id="uuidProvider")),
    ]

    result = tested.handle()
    expected = [Effect(type="LOG", payload="SomePayload")]
    assert result == expected

    calls = [
        call.presigned_url(
            "theApiSigningKey",
            "/plugin-io/api/hyperscribe/transcript",
            {"patient_id": "uuidPatient", "note_id": "uuidNote"},
        ),
    ]
    assert authenticator.mock_calls == calls
    calls = [call(url="preSignedUrl", target="new_window"), call().apply()]
    assert launch_modal_effect.mock_calls == calls
    calls = [call.get(dbid="noteId")]
    assert note_db.mock_calls == calls

    reset_mocks()


@patch.object(Helper, "editable_note")
def test_visible(editable_note):
    def reset_mocks():
        editable_note.reset_mock()

    tests = [
        ("yes", "userId", "no", True),
        ("yes", "anotherId", "no", True),
        ("yes", "otherId", "no", False),
        ("no", "userId", "no", False),
        ("no", "anotherId", "no", False),
        ("no", "otherId", "no", True),
        #
        ("yes", "userId", "yes", False),
        ("yes", "anotherId", "yes", False),
        ("no", "otherId", "yes", False),
    ]
    for policy, staff_id, tuning, expected in tests:
        for editable in [True, False]:
            editable_note.side_effect = [editable]
            event = Event(EventRequest(context=json.dumps({"note_id": 778, "user": {"id": staff_id}})))
            secrets = {
                "AudioHost": "theAudioHost",
                "KeyTextLLM": "theKeyTextLLM",
                "VendorTextLLM": "theVendorTextLLM",
                "KeyAudioLLM": "theKeyAudioLLM",
                "VendorAudioLLM": "theVendorAudioLLM",
                "StructuredReasonForVisit": "yes",
                "AuditLLMDecisions": "no",
                "IsTuning": tuning,
                "AwsKey": "theKey",
                "AwsSecret": "theSecret",
                "AwsRegion": "theRegion",
                "AwsBucketLogs": "theBucketLogs",
                "APISigningKey": "theApiSigningKey",
                "StaffersList": "userId, anotherId",
                "StaffersPolicy": policy,
            }
            tested = TranscriptButton(event, secrets)
            assert tested.visible() is (expected and editable)

            calls = []
            if expected:
                calls = [call(778)]
            assert editable_note.mock_calls == calls
            reset_mocks()
