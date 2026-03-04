from unittest.mock import call, patch

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.handlers.action_button import ActionButton

from hyperscribe.scribe.record_button import RecordButton
from tests.helper import is_constant


def test_class() -> None:
    assert issubclass(RecordButton, ActionButton)


def test_constants() -> None:
    constants = {
        "BUTTON_TITLE": "Record",
        "BUTTON_KEY": "SCRIBE_RECORD",
        "BUTTON_LOCATION": "note_header",
        "RESPONDS_TO": ["SHOW_NOTE_HEADER_BUTTON", "ACTION_BUTTON_CLICKED"],
        "PRIORITY": 0,
    }
    assert is_constant(RecordButton, constants)


def test_visible() -> None:
    tests = [
        ("scribe", True),
        ("Scribe", True),
        ("SCRIBE", True),
        ("hyperscribe", False),
        ("", False),
    ]
    for modality, expected in tests:
        event = Event(EventRequest())
        secrets = {"Modality": modality}
        tested = RecordButton(event, secrets)
        assert tested.visible() is expected, f"modality={modality!r}"


def test_visible_missing_secret() -> None:
    event = Event(EventRequest())
    tested = RecordButton(event, {})
    assert tested.visible() is False


@patch("hyperscribe.scribe.record_button.LaunchModalEffect")
def test_handle(launch_modal_effect: object) -> None:
    launch_modal_effect.return_value.apply.side_effect = [  # type: ignore[union-attr]
        Effect(type="LOG", payload="SomePayload")
    ]
    launch_modal_effect.TargetType.RIGHT_CHART_PANE = "right_chart_pane"  # type: ignore[union-attr]

    event = Event(EventRequest(context='{"note_id":5481}'))
    tested = RecordButton(event, {})
    result = tested.handle()

    assert result == [Effect(type="LOG", payload="SomePayload")]
    assert launch_modal_effect.mock_calls == [  # type: ignore[union-attr]
        call(
            url="/plugin-io/api/hyperscribe/scribe/app?note_dbid=5481&view=record",
            target="right_chart_pane",
            title="Record",
        ),
        call().apply(),
    ]
