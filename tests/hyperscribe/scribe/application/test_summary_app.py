from unittest.mock import MagicMock, call, patch

from django.db.models import QuerySet

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event

from hyperscribe.scribe.application.summary_app import SummaryApp


def test_constants() -> None:
    assert SummaryApp.NAME == "Summary"
    assert SummaryApp.IDENTIFIER == "hyperscribe__scribe_summary"


@patch("hyperscribe.scribe.application.summary_app.Settings")
def test_visible(mock_settings_cls: MagicMock) -> None:
    mock_settings = MagicMock()
    mock_settings_cls.from_dictionary.return_value = mock_settings

    # scribe modality for this staff → visible
    mock_settings.is_scribe_modality.return_value = True
    event = Event(EventRequest(context='{"user": {"id": "staff1"}}'))
    tested = SummaryApp(event, {"Modality": "scribe"})
    assert tested.visible() is True
    mock_settings.is_scribe_modality.assert_called_with("staff1")

    # not scribe modality for this staff → not visible
    mock_settings.is_scribe_modality.return_value = False
    event = Event(EventRequest(context='{"user": {"id": "staff2"}}'))
    tested = SummaryApp(event, {"Modality": "copilot"})
    assert tested.visible() is False
    mock_settings.is_scribe_modality.assert_called_with("staff2")


@patch("hyperscribe.scribe.application.summary_app.Settings")
def test_visible_missing_user_context(mock_settings_cls: MagicMock) -> None:
    mock_settings = MagicMock()
    mock_settings_cls.from_dictionary.return_value = mock_settings
    mock_settings.is_scribe_modality.return_value = False

    event = Event(EventRequest())
    tested = SummaryApp(event, {})
    assert tested.visible() is False
    mock_settings.is_scribe_modality.assert_called_with("")


@patch("canvas_sdk.v1.data.note.Note")
@patch("hyperscribe.scribe.application.summary_app.LaunchModalEffect")
def test_handle(launch_modal_effect: object, mock_note: MagicMock) -> None:
    launch_modal_effect.return_value.apply.side_effect = [  # type: ignore[union-attr]
        Effect(type="LOG", payload="SomePayload")
    ]
    launch_modal_effect.TargetType.NOTE = "note"  # type: ignore[union-attr]
    mock_qs = MagicMock(spec=QuerySet)
    mock_qs.get.return_value = "uuid-5481"
    mock_note.objects.values_list.return_value = mock_qs

    event = Event(EventRequest(context='{"note_id":5481}'))
    tested = SummaryApp(event, {})
    result = tested.handle()

    assert result == [Effect(type="LOG", payload="SomePayload")]
    mock_qs.get.assert_called_once_with(dbid=5481)
    assert launch_modal_effect.mock_calls == [  # type: ignore[union-attr]
        call(
            url="/plugin-io/api/hyperscribe/scribe/app?note_id=uuid-5481&view=summary",
            target="note",
            title="Summary",
        ),
        call().apply(),
    ]
