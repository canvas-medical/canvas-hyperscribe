from unittest.mock import call, patch

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.handlers.application import NoteApplication

from hyperscribe.scribe.transcript_app import TranscriptApp


def test_class() -> None:
    assert issubclass(TranscriptApp, NoteApplication)
    assert issubclass(TranscriptApp, ActionButton)


def test_constants() -> None:
    assert TranscriptApp.NAME == "Transcript"
    assert TranscriptApp.IDENTIFIER == "hyperscribe__scribe_transcript"


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
        tested = TranscriptApp(event, secrets)
        assert tested.visible() is expected, f"modality={modality!r}"


def test_visible_missing_secret() -> None:
    event = Event(EventRequest())
    tested = TranscriptApp(event, {})
    assert tested.visible() is False


@patch("hyperscribe.scribe.transcript_app.LaunchModalEffect")
def test_handle(launch_modal_effect: object) -> None:
    launch_modal_effect.return_value.apply.side_effect = [  # type: ignore[union-attr]
        Effect(type="LOG", payload="SomePayload")
    ]
    launch_modal_effect.TargetType.NOTE = "note"  # type: ignore[union-attr]

    event = Event(EventRequest(context='{"note_id":5481}'))
    tested = TranscriptApp(event, {})
    result = tested.handle()

    assert result == [Effect(type="LOG", payload="SomePayload")]
    assert launch_modal_effect.mock_calls == [  # type: ignore[union-attr]
        call(
            url="/plugin-io/api/hyperscribe/scribe/app?note_dbid=5481&view=transcript",
            target="note",
            title="Transcript",
        ),
        call().apply(),
    ]
