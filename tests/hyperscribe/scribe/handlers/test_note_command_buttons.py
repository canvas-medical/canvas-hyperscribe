from unittest.mock import MagicMock, patch

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.effects.configure_command_buttons import ConfigureCommandButtons
from canvas_sdk.events import Event, EventType
from canvas_sdk.handlers.base import BaseHandler

from hyperscribe.scribe.handlers.note_command_buttons import NoteCommandButtonsRestoreHandler

MODULE = "hyperscribe.scribe.handlers.note_command_buttons"


def test_class() -> None:
    assert issubclass(NoteCommandButtonsRestoreHandler, BaseHandler)


def test_responds_to_note_closed() -> None:
    assert NoteCommandButtonsRestoreHandler.RESPONDS_TO == [EventType.Name(EventType.NOTE_CLOSED)]


@patch(f"{MODULE}.configure_command_buttons_effect")
def test_restores_visible_for_patient(mock_restore: MagicMock) -> None:
    mock_restore.return_value = Effect(type="LOG", payload="RestoreButtons")

    # NOTE_CLOSED targets the patient.
    event = Event(EventRequest(target="patient-uuid"))
    tested = NoteCommandButtonsRestoreHandler(event, {})
    result = tested.compute()

    assert result == [Effect(type="LOG", payload="RestoreButtons")]
    mock_restore.assert_called_once_with("patient-uuid", ConfigureCommandButtons.Visibility.VISIBLE)


@patch(f"{MODULE}.configure_command_buttons_effect")
def test_no_effect_without_patient(mock_restore: MagicMock) -> None:
    event = Event(EventRequest(target=""))
    tested = NoteCommandButtonsRestoreHandler(event, {})
    assert tested.compute() == []
    mock_restore.assert_not_called()
