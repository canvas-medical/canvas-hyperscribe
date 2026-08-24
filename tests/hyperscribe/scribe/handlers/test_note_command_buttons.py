from unittest.mock import MagicMock, patch

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.effects.configure_command_buttons import ConfigureCommandButtons
from canvas_sdk.events import Event, EventType
from canvas_sdk.handlers.base import BaseHandler

from hyperscribe.scribe.handlers.note_command_buttons import (
    NoteCommandButtonsRestoreHandler,
    NoteSignedCommandButtonsRestoreHandler,
)

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


# --- NoteSignedCommandButtonsRestoreHandler ---
#
# Signing auto-collapses the note, which emits neither NOTE_TAB_CHANGE nor
# NOTE_CLOSED, so this handler is the only thing that un-hides the buttons on the
# sign path.


def test_signed_handler_class() -> None:
    assert issubclass(NoteSignedCommandButtonsRestoreHandler, BaseHandler)


def test_signed_handler_responds_to_state_change_created() -> None:
    assert NoteSignedCommandButtonsRestoreHandler.RESPONDS_TO == [
        EventType.Name(EventType.NOTE_STATE_CHANGE_EVENT_CREATED)
    ]


@patch(f"{MODULE}.NoteStateChangeEvent")
@patch(f"{MODULE}.configure_command_buttons_effect")
def test_signed_restores_visible_for_patient(mock_restore: MagicMock, mock_model: MagicMock) -> None:
    mock_restore.return_value = Effect(type="LOG", payload="RestoreButtons")
    mock_model.objects.values.return_value.get.return_value = {
        "state": "LKD",
        "note__patient__id": "patient-uuid",
    }
    mock_model.DoesNotExist = Exception

    event = Event(EventRequest(target="state-event-uuid"))
    result = NoteSignedCommandButtonsRestoreHandler(event, {}).compute()

    assert result == [Effect(type="LOG", payload="RestoreButtons")]
    mock_restore.assert_called_once_with("patient-uuid", ConfigureCommandButtons.Visibility.VISIBLE)
    # Resolved off the state-change event id, in a single two-column query.
    mock_model.objects.values.assert_called_once_with("state", "note__patient__id")
    mock_model.objects.values.return_value.get.assert_called_once_with(id="state-event-uuid")


@patch(f"{MODULE}.NoteStateChangeEvent")
@patch(f"{MODULE}.configure_command_buttons_effect")
def test_signed_restores_for_every_non_editable_state(mock_restore: MagicMock, mock_model: MagicMock) -> None:
    mock_restore.return_value = Effect(type="LOG", payload="RestoreButtons")
    mock_model.DoesNotExist = Exception
    # LKD/SGN are the sign paths; RLK/DLT/CLD also leave the note uneditable.
    for state in ("LKD", "SGN", "RLK", "DLT", "CLD"):
        mock_restore.reset_mock()
        mock_model.objects.values.return_value.get.return_value = {
            "state": state,
            "note__patient__id": "patient-uuid",
        }
        event = Event(EventRequest(target="state-event-uuid"))
        assert NoteSignedCommandButtonsRestoreHandler(event, {}).compute() == [
            Effect(type="LOG", payload="RestoreButtons")
        ], f"expected a restore for state {state}"
        mock_restore.assert_called_once_with("patient-uuid", ConfigureCommandButtons.Visibility.VISIBLE)


@patch(f"{MODULE}.NoteStateChangeEvent")
@patch(f"{MODULE}.configure_command_buttons_effect")
def test_signed_ignores_editable_states(mock_restore: MagicMock, mock_model: MagicMock) -> None:
    # Transitions back INTO an editable state (e.g. unlock-for-amend) need no
    # restore: reopening the note reopens the Scribe tab, which re-asserts the hide.
    mock_model.DoesNotExist = Exception
    for state in ("NEW", "PSH", "ULK", "RST", "UND", "CVD"):
        mock_model.objects.values.return_value.get.return_value = {
            "state": state,
            "note__patient__id": "patient-uuid",
        }
        event = Event(EventRequest(target="state-event-uuid"))
        assert NoteSignedCommandButtonsRestoreHandler(event, {}).compute() == [], f"unexpected restore for {state}"
    mock_restore.assert_not_called()


@patch(f"{MODULE}.NoteStateChangeEvent")
@patch(f"{MODULE}.configure_command_buttons_effect")
def test_signed_no_effect_when_note_has_no_patient(mock_restore: MagicMock, mock_model: MagicMock) -> None:
    mock_model.objects.values.return_value.get.return_value = {"state": "LKD", "note__patient__id": None}
    mock_model.DoesNotExist = Exception

    event = Event(EventRequest(target="state-event-uuid"))
    assert NoteSignedCommandButtonsRestoreHandler(event, {}).compute() == []
    mock_restore.assert_not_called()


@patch(f"{MODULE}.NoteStateChangeEvent")
@patch(f"{MODULE}.configure_command_buttons_effect")
def test_signed_no_effect_when_state_event_missing(mock_restore: MagicMock, mock_model: MagicMock) -> None:
    class DoesNotExist(Exception):
        pass

    mock_model.DoesNotExist = DoesNotExist
    mock_model.objects.values.return_value.get.side_effect = DoesNotExist()

    event = Event(EventRequest(target="state-event-uuid"))
    assert NoteSignedCommandButtonsRestoreHandler(event, {}).compute() == []
    mock_restore.assert_not_called()


@patch(f"{MODULE}.NoteStateChangeEvent")
@patch(f"{MODULE}.configure_command_buttons_effect")
def test_signed_restore_is_not_gated_on_scribe_usage(mock_restore: MagicMock, mock_model: MagicMock) -> None:
    """A note whose Scribe tab default-opened but was never written to still hid
    the buttons via ScribeApp.handle(), so it must still restore on sign. This
    pins the deliberate absence of the has-ScribeTranscript/ScribeSummary gate
    that NoteStateHandler applies — adding one here would strand the buttons."""
    mock_restore.return_value = Effect(type="LOG", payload="RestoreButtons")
    mock_model.objects.values.return_value.get.return_value = {
        "state": "LKD",
        "note__patient__id": "patient-uuid",
    }
    mock_model.DoesNotExist = Exception

    with patch(f"{MODULE}.ScribeSummary", create=True) as mock_summary:
        with patch(f"{MODULE}.ScribeTranscript", create=True) as mock_transcript:
            event = Event(EventRequest(target="state-event-uuid"))
            assert NoteSignedCommandButtonsRestoreHandler(event, {}).compute() == [
                Effect(type="LOG", payload="RestoreButtons")
            ]
            mock_summary.objects.filter.assert_not_called()
            mock_transcript.objects.filter.assert_not_called()
