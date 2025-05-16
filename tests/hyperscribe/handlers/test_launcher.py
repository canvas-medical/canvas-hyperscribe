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
            url='https://the.audio.server/path/to/audios/capture/targetId/uuidNote?'
                'interval=7&'
                'end_flag=EOF&'
                'progress=https%3A%2F%2Fthe.presigned.url%3Fparam1%3Dvalue1%26param2%3Dvalue2',
            target='right_chart_pane'),
        call().apply(),
    ]
    assert launch_model_effect.mock_calls == calls
    calls = [
        call.presigned_url(
            'theApiSigningKey',
            '/plugin-io/api/hyperscribe/progress',
            {'note_id': 'uuidNote'},
        )
    ]
    assert authenticator.mock_calls == calls
    calls = [call.get(dbid='noteId')]
    assert note_db.mock_calls == calls
    reset_mocks()


def test_visible():
    event = Event(EventRequest())
    tested = Launcher(event)
    assert tested.visible() is True
