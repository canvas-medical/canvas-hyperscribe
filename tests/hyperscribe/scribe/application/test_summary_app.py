from unittest.mock import MagicMock, call, patch

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event

from hyperscribe.scribe.application.summary_app import SummaryApp


def test_constants() -> None:
    assert SummaryApp.NAME == "Summary"
    assert SummaryApp.IDENTIFIER == "hyperscribe__scribe_summary"


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
        tested = SummaryApp(event, secrets)
        assert tested.visible() is expected, f"modality={modality!r}"


def test_visible_missing_secret() -> None:
    event = Event(EventRequest())
    tested = SummaryApp(event, {})
    assert tested.visible() is False


@patch("canvas_sdk.v1.data.note.Note")
@patch("hyperscribe.scribe.application.summary_app.LaunchModalEffect")
def test_handle(launch_modal_effect: object, mock_note: MagicMock) -> None:
    launch_modal_effect.return_value.apply.side_effect = [  # type: ignore[union-attr]
        Effect(type="LOG", payload="SomePayload")
    ]
    launch_modal_effect.TargetType.NOTE = "note"  # type: ignore[union-attr]
    mock_note.objects.values_list.return_value.get.return_value = "uuid-5481"

    event = Event(EventRequest(context='{"note_id":5481}'))
    tested = SummaryApp(event, {})
    result = tested.handle()

    assert result == [Effect(type="LOG", payload="SomePayload")]
    mock_note.objects.values_list.return_value.get.assert_called_once_with(dbid=5481)
    assert launch_modal_effect.mock_calls == [  # type: ignore[union-attr]
        call(
            url="/plugin-io/api/hyperscribe/scribe/app?note_id=uuid-5481&view=summary",
            target="note",
            title="Summary",
        ),
        call().apply(),
    ]
