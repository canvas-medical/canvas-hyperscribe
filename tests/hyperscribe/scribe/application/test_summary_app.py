from unittest.mock import call, patch

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


@patch("hyperscribe.scribe.application.summary_app.LaunchModalEffect")
def test_handle(launch_modal_effect: object) -> None:
    launch_modal_effect.return_value.apply.side_effect = [  # type: ignore[union-attr]
        Effect(type="LOG", payload="SomePayload")
    ]
    launch_modal_effect.TargetType.NOTE = "note"  # type: ignore[union-attr]

    event = Event(EventRequest(context='{"note_id":5481}'))
    tested = SummaryApp(event, {})
    result = tested.handle()

    assert result == [Effect(type="LOG", payload="SomePayload")]
    assert launch_modal_effect.mock_calls == [  # type: ignore[union-attr]
        call(
            url="/plugin-io/api/hyperscribe/scribe/app?note_dbid=5481&view=summary",
            target="note",
            title="Summary",
        ),
        call().apply(),
    ]
