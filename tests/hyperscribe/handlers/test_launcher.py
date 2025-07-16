import json
from unittest.mock import patch, call

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.events.base import TargetType
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.v1.data import Note, Patient

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
@patch('hyperscribe.handlers.launcher.Authenticator')
@patch('hyperscribe.handlers.launcher.LaunchModalEffect')
def test_handle(launch_modal_effect, authenticator, note_db):
    def reset_mocks():
        launch_modal_effect.reset_mock()
        authenticator.reset_mock()
        note_db.reset_mock()

    launch_modal_effect.return_value.apply.side_effect = [Effect(type="LOG", payload="SomePayload")]
    launch_modal_effect.TargetType.RIGHT_CHART_PANE = "right_chart_pane"
    authenticator.presigned_url.side_effect = ["/plugin-io/api/hyperscribe/capture/patientId/noteId"]
    note_db.get.return_value.id = "noteId"

    event = Event(EventRequest(context='{"note_id":"noteId"}'))
    event.target = TargetType(id="patientId", type=Patient)
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
            url='/plugin-io/api/hyperscribe/capture/patientId/noteId',
            target='right_chart_pane',
            title='Hyperscribe'),
        call().apply(),
    ]
    assert launch_modal_effect.mock_calls == calls
    calls = [
        call.presigned_url(
            'theApiSigningKey',
            '/plugin-io/api/hyperscribe/capture/patientId/noteId',
            {},
        )
    ]
    assert authenticator.mock_calls == calls
    calls = [call.get(dbid='noteId')]
    assert note_db.mock_calls == calls
    reset_mocks()


def test_visible():
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
        event = Event(EventRequest(context=json.dumps({"note_id": "noteId", "user": {"id": staff_id}})))
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
        assert tested.visible() is expected
