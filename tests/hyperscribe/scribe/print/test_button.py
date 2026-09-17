import json
from unittest.mock import MagicMock, call, patch

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.handlers.action_button import ActionButton

from hyperscribe.scribe.print.button import PrintScribeNoteButton
from tests.helper import is_constant


def test_class() -> None:
    assert issubclass(PrintScribeNoteButton, ActionButton)


def test_constants() -> None:
    constants = {
        "BUTTON_TITLE": "🖨️ Scribe Note",
        "BUTTON_KEY": "HYPERSCRIBE_PRINT_SCRIBE_NOTE",
        "BUTTON_LOCATION": "note_header_dropdown",
        "BUTTON_BACKGROUND_COLOR": None,
        "BUTTON_TEXT_COLOR": None,
        "RESPONDS_TO": ActionButton.RESPONDS_TO,
        "PRIORITY": 0,
    }
    assert is_constant(PrintScribeNoteButton, constants)


@patch("hyperscribe.scribe.print.button.is_scribe_visible")
def test_visible_delegates_to_is_scribe_visible(mock_is_visible: MagicMock) -> None:
    secrets = {"Modality": "scribe", "ScribeNoteTypes": "Office Visit"}
    event = Event(EventRequest(context='{"note_id": 1}'))

    mock_is_visible.return_value = True
    button = PrintScribeNoteButton(event, secrets)
    assert button.visible() is True
    mock_is_visible.assert_called_once_with(secrets, button.event)

    mock_is_visible.reset_mock()
    mock_is_visible.return_value = False
    button = PrintScribeNoteButton(event, secrets)
    assert button.visible() is False


@patch("hyperscribe.scribe.print.button.LaunchModalEffect")
def test_handle_returns_modal_effect(launch_modal_effect: MagicMock) -> None:
    launch_modal_effect.return_value.apply.return_value = Effect(type="LOG", payload="ModalPayload")
    launch_modal_effect.TargetType.DEFAULT_MODAL = "default_modal"

    event = Event(EventRequest(context=json.dumps({"note_id": 5481})))
    tested = PrintScribeNoteButton(event, {})

    result = tested.handle()

    assert result == [Effect(type="LOG", payload="ModalPayload")]
    assert launch_modal_effect.mock_calls == [
        call(
            url="/plugin-io/api/hyperscribe/scribe-print/note/5481",
            target="default_modal",
            title="Print Scribe Note",
        ),
        call().apply(),
    ]
