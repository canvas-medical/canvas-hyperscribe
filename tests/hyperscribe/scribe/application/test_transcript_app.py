from unittest.mock import call, patch

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
        tested = ScribeApp(event, secrets)
        assert tested.visible() is expected, f"modality={modality!r}"


def test_visible_missing_secret() -> None:
    event = Event(EventRequest())
    tested = ScribeApp(event, {})
    assert tested.visible() is False


@patch("hyperscribe.scribe.application.transcript_app.LaunchModalEffect")
def test_handle(launch_modal_effect: object) -> None:
    launch_modal_effect.return_value.apply.side_effect = [  # type: ignore[union-attr]
        Effect(type="LOG", payload="SomePayload")
    ]
    launch_modal_effect.TargetType.NOTE = "note"  # type: ignore[union-attr]

    event = Event(EventRequest(context='{"note_id":5481}'))
    tested = ScribeApp(event, {})
    result = tested.handle()

    assert result == [Effect(type="LOG", payload="SomePayload")]
    assert launch_modal_effect.mock_calls == [  # type: ignore[union-attr]
        call(
            url="/plugin-io/api/hyperscribe/scribe/app?note_dbid=5481&view=scribe",
            target="note",
            title="Scribe",
        ),
        call().apply(),
    ]
