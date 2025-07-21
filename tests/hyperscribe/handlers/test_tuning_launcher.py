import json
from time import time
from unittest.mock import patch, call

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.events.base import TargetType
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.v1.data.note import Note, CurrentNoteStateEvent
from canvas_sdk.v1.data.patient import Patient

from hyperscribe.handlers.tuning_launcher import TuningLauncher
from tests.helper import is_constant


def test_class():
    tested = TuningLauncher
    assert issubclass(tested, ActionButton)


def test_constants():
    tested = TuningLauncher
    constants = {
        "BUTTON_TITLE": "🧪 Hyperscribe Tuning",
        "BUTTON_KEY": "HYPERSCRIBE_TUNING_LAUNCHER",
        "BUTTON_LOCATION": "note_header",
        "RESPONDS_TO": ["SHOW_NOTE_HEADER_BUTTON", "ACTION_BUTTON_CLICKED"],
        "PRIORITY": 0,
    }
    assert is_constant(tested, constants)


@patch("hyperscribe.handlers.tuning_launcher.time", wraps=time)
@patch.object(Note, "objects")
@patch('hyperscribe.handlers.tuning_launcher.LaunchModalEffect')
def test_handle(launch_model_effect, note_db, mock_time):
    def reset_mocks():
        launch_model_effect.reset_mock()
        note_db.reset_mock()
        mock_time.reset_mock()

    launch_model_effect.return_value.apply.side_effect = [Effect(type="LOG", payload="SomePayload")]
    launch_model_effect.TargetType.NEW_WINDOW = "new_window"
    note_db.get.return_value.id = "uuidNote"

    mock_time.side_effect = [1741964291.775192]

    event = Event(EventRequest(context='{"note_id":"noteId"}'))
    event.target = TargetType(id="targetId", type=Patient)
    secrets = {
        "AudioIntervalSeconds": 7,
        "APISigningKey": "theApiSigningKey",
    }
    tested = TuningLauncher(event, secrets)
    result = tested.handle()
    expected = [Effect(type="LOG", payload="SomePayload")]
    assert result == expected

    calls = [
        call(
            url='/plugin-io/api/hyperscribe/archive'
                '?note_id=uuidNote'
                '&patient_id=targetId'
                '&interval=7'
                '&ts=1741964291'
                '&sig=ceb81ba49d3a2f950b0327a9af6a6fe7677994b8467ba076f9953a9171b9728a',
            target='new_window',
        ),
        call().apply(),
    ]
    assert launch_model_effect.mock_calls == calls
    calls = [call.get(dbid='noteId')]
    assert note_db.mock_calls == calls
    calls = [call()]
    assert mock_time.mock_calls == calls
    reset_mocks()


@patch.object(CurrentNoteStateEvent, "objects")
def test_visible(last_note_state_event_db):
    def reset_mocks():
        last_note_state_event_db.reset_mock()

    tests = [
        ("yes", "userId", "yes", True),
        ("yes", "someId", "yes", True),
        ("yes", "otherId", "yes", False),
        ("no", "userId", "yes", False),
        ("no", "someId", "yes", False),
        ("no", "otherId", "yes", True),
        #
        ("yes", "userId", "no", False),
        ("yes", "someId", "no", False),
        ("no", "otherId", "no", False),
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
                "StaffersList": "userId, someId",
                "StaffersPolicy": policy,
            }
            tested = TuningLauncher(event, secrets)
            assert tested.visible() is (expected and editable)

            calls = []
            if expected:
                calls = [
                    call.get(note_id=778),
                    call.get().editable(),
                ]
            assert last_note_state_event_db.mock_calls == calls
            reset_mocks()
