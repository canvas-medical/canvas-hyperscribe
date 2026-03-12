from unittest.mock import MagicMock, call, patch

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.handlers.application import NoteApplication

from hyperscribe.scribe.application.transcript_app import ScribeApp


def test_class() -> None:
    assert issubclass(ScribeApp, NoteApplication)
    assert issubclass(ScribeApp, ActionButton)


def test_constants() -> None:
    assert ScribeApp.NAME == "Scribe"
    assert ScribeApp.IDENTIFIER == "hyperscribe__scribe"


@patch("hyperscribe.scribe.application.transcript_app.Settings")
def test_visible(mock_settings_cls: MagicMock) -> None:
    mock_settings = MagicMock()
    mock_settings_cls.from_dictionary.return_value = mock_settings

    # scribe modality for this staff → visible
    mock_settings.is_scribe_modality.return_value = True
    event = Event(EventRequest(context='{"user": {"id": "staff1"}}'))
    tested = ScribeApp(event, {"Modality": "scribe"})
    assert tested.visible() is True
    mock_settings.is_scribe_modality.assert_called_with("staff1")

    # not scribe modality for this staff → not visible
    mock_settings.is_scribe_modality.return_value = False
    event = Event(EventRequest(context='{"user": {"id": "staff2"}}'))
    tested = ScribeApp(event, {"Modality": "copilot"})
    assert tested.visible() is False
    mock_settings.is_scribe_modality.assert_called_with("staff2")


@patch("hyperscribe.scribe.application.transcript_app.Settings")
def test_visible_missing_user_context(mock_settings_cls: MagicMock) -> None:
    mock_settings = MagicMock()
    mock_settings_cls.from_dictionary.return_value = mock_settings
    mock_settings.is_scribe_modality.return_value = False

    event = Event(EventRequest())
    tested = ScribeApp(event, {})
    assert tested.visible() is False
    mock_settings.is_scribe_modality.assert_called_with("")


@patch("hyperscribe.scribe.application.transcript_app.Note")
@patch("hyperscribe.scribe.application.transcript_app.LaunchModalEffect")
def test_handle(launch_modal_effect: object, mock_note: MagicMock) -> None:
    launch_modal_effect.return_value.apply.side_effect = [  # type: ignore[union-attr]
        Effect(type="LOG", payload="SomePayload")
    ]
    launch_modal_effect.TargetType.NOTE = "note"  # type: ignore[union-attr]
    mock_note.objects.values_list.return_value.get.return_value = "uuid-5481"

    event = Event(EventRequest(context='{"note_id":5481}'))
    tested = ScribeApp(event, {})
    result = tested.handle()

    assert result == [Effect(type="LOG", payload="SomePayload")]
    mock_note.objects.values_list.return_value.get.assert_called_once_with(dbid=5481)
    assert launch_modal_effect.mock_calls == [  # type: ignore[union-attr]
        call(
            url="/plugin-io/api/hyperscribe/scribe/app?note_id=uuid-5481&view=scribe",
            target="note",
            title="Scribe",
        ),
        call().apply(),
    ]
