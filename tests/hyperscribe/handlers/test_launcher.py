import json
from unittest.mock import patch, call

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.events.base import TargetType
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.v1.data.note import Note, NoteStateChangeEvent, NoteStates
from canvas_sdk.v1.data.patient import Patient

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
def test_handle(launch_modal_effect, authenticator, note_db):
    def reset_mocks():
        launch_modal_effect.reset_mock()
        authenticator.reset_mock()
        note_db.reset_mock()

    launch_modal_effect.return_value.apply.side_effect = [Effect(type="LOG", payload="SomePayload")]
    launch_modal_effect.TargetType.RIGHT_CHART_PANE = "right_chart_pane"
    authenticator.presigned_url.side_effect = ["/plugin-io/api/hyperscribe/capture/patientId/noteId/5481"]
    note_db.get.side_effect = [Note(id="noteId", dbid=5481)]

    event = Event(EventRequest(context='{"note_id":5481}'))
    event.target = TargetType(id="patientId", type=Patient)
    secrets = {
        "AudioHost": "https://the.audio.server/path/to/audios/",
        "AudioIntervalSeconds": 7,
        "APISigningKey": "theApiSigningKey",
        "CopilotsTeamFHIRGroupId": "theCopilotsTeamFHIRGroupId",
    }
    environment = {"CUSTOMER_IDENTIFIER": "theTestEnv"}
    tested = Launcher(event, secrets, environment)
    result = tested.handle()
    expected = [Effect(type="LOG", payload="SomePayload")]
    assert result == expected

    calls = [
        call(
            url="/plugin-io/api/hyperscribe/capture/patientId/noteId/5481",
            target="right_chart_pane",
            title="Hyperscribe",
        ),
        call().apply(),
    ]
    assert launch_modal_effect.mock_calls == calls
    calls = [
        call.presigned_url(
            "theApiSigningKey",
            "/plugin-io/api/hyperscribe/capture/patientId/noteId/5481",
            {},
        )
    ]
    assert authenticator.mock_calls == calls
    calls = [call.get(dbid=5481)]
    assert note_db.mock_calls == calls
    reset_mocks()


@patch.object(NoteStateChangeEvent, "objects")
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
            last_note_state_event_db.filter.return_value.order_by.return_value.last.return_value.state = (
                NoteStates.NEW if editable else NoteStates.LOCKED
            )
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
                "TrialStaffersList": "",
            }
            tested = Launcher(event, secrets)
            assert tested.visible() is (expected and editable)
            exp_button_title = "🖊️ Hyperscribe"
            if expected and editable:
                exp_button_title = "🖊️ Hyperscribe (778)"
            assert tested.BUTTON_TITLE == exp_button_title

            calls = []
            if tuning == "no":  # Only check note state when not tuning
                calls = [
                    call.filter(note_id=778),
                    call.filter().order_by("id"),
                    call.filter().order_by().last(),
                    call.filter().order_by().last().__bool__(),
                ]
            assert last_note_state_event_db.mock_calls == calls
            reset_mocks()
