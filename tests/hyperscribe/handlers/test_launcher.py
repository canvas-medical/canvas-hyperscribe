import json
from unittest.mock import patch, call

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.events.base import TargetType
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.v1.data.patient import Patient
from canvas_sdk.v1.data.note import Note, CurrentNoteStateEvent

from hyperscribe.handlers.launcher import Launcher
from tests.helper import is_constant


def test_class():
    tested = Launcher
    assert issubclass(tested, ActionButton)


def test_constants():
    tested = Launcher
    constants = {
        "BUTTON_TITLE": "🖊️ Hyperscribe",
        "BUTTON_KEY": "HYPERSCRIBE_LAUNCHER",
        "BUTTON_LOCATION": "note_header",
        "RESPONDS_TO": ["SHOW_NOTE_HEADER_BUTTON", "ACTION_BUTTON_CLICKED"],
        "PRIORITY": 0,
    }
    assert is_constant(tested, constants)


@patch.object(Note, "objects")
@patch("hyperscribe.handlers.launcher.Authenticator")
@patch("hyperscribe.handlers.launcher.LaunchModalEffect")
def test_handle(launch_model_effect, authenticator, note_db):
    def reset_mocks():
        launch_model_effect.reset_mock()
        authenticator.reset_mock()
        note_db.reset_mock()

    launch_model_effect.return_value.apply.side_effect = [Effect(type="LOG", payload="SomePayload")]
    launch_model_effect.TargetType.RIGHT_CHART_PANE = "right_chart_pane"
    authenticator.presigned_url.side_effect = ["https://the.presigned.url?param1=value1&param2=value2"]
    note_db.get.return_value.id = "uuidNote"

    event = Event(EventRequest(context='{"note_id":"noteId"}'))
    event.target = TargetType(id="targetId", type=Patient)
    secrets = {
        "AudioHost": "https://the.audio.server/path/to/audios/",
        "AudioIntervalSeconds": 7,
        "APISigningKey": "theApiSigningKey",
    }
    environment = {"CUSTOMER_IDENTIFIER": "theTestEnv"}
    tested = Launcher(event, secrets, environment)
    result = tested.handle()
    expected = [Effect(type="LOG", payload="SomePayload")]
    assert result == expected

    calls = [
        call(
            url="https://the.audio.server/path/to/audios/capture/targetId/uuidNote?"
            "interval=7&"
            "end_flag=EOF&"
            "progress=https%3A%2F%2Fthe.presigned.url%3Fparam1%3Dvalue1%26param2%3Dvalue2",
            target="right_chart_pane",
        ),
        call().apply(),
    ]
    assert launch_model_effect.mock_calls == calls
    calls = [
        call.presigned_url(
            "theApiSigningKey",
            "https://theTestEnv.canvasmedical.com/plugin-io/api/hyperscribe/progress",
            {"note_id": "uuidNote"},
        ),
    ]
    assert authenticator.mock_calls == calls
    calls = [call.get(dbid="noteId")]
    assert note_db.mock_calls == calls
    reset_mocks()


@patch.object(CurrentNoteStateEvent, "objects")
def test_visible(last_note_state_event_db):
    def reset_mocks():
        last_note_state_event_db.reset_mock()

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
            tested = Launcher(event, secrets)
            assert tested.visible() is (expected and editable)

            calls = []
            if expected:
                calls = [call.get(note_id=778), call.get().editable()]
            assert last_note_state_event_db.mock_calls == calls
            reset_mocks()
