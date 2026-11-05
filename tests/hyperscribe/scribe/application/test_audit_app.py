from __future__ import annotations

from unittest.mock import MagicMock, call, patch

from django.db.models import QuerySet

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.handlers.application import NoteApplication

from hyperscribe.scribe.application.audit_app import ScribeAuditApp


def test_class() -> None:
    assert issubclass(ScribeAuditApp, NoteApplication)


def test_constants() -> None:
    assert ScribeAuditApp.NAME == "Audit"
    assert ScribeAuditApp.IDENTIFIER == "hyperscribe__scribe_audit"


@patch("hyperscribe.scribe.application.audit_app.is_debug_visible")
def test_visible_no_debug_staffers(mock_is_debug: MagicMock) -> None:
    mock_is_debug.return_value = False
    event = Event(EventRequest(context='{"user": {"id": "staff1"}}'))
    tested = ScribeAuditApp(event, {"Modality": "scribe"})
    assert tested.visible() is False


@patch("hyperscribe.scribe.application.audit_app.is_debug_visible")
def test_visible_staff_in_list(mock_is_debug: MagicMock) -> None:
    mock_is_debug.return_value = True
    event = Event(EventRequest(context='{"user": {"id": "staff1"}}'))
    tested = ScribeAuditApp(event, {"Modality": "scribe", "ScribeDebugStaffers": "staff1,staff2"})
    assert tested.visible() is True


@patch("hyperscribe.scribe.application.audit_app.is_debug_visible")
def test_visible_staff_not_in_list(mock_is_debug: MagicMock) -> None:
    mock_is_debug.return_value = False
    event = Event(EventRequest(context='{"user": {"id": "staff3"}}'))
    tested = ScribeAuditApp(event, {"Modality": "scribe", "ScribeDebugStaffers": "staff1,staff2"})
    assert tested.visible() is False


@patch("hyperscribe.scribe.application.audit_app.is_debug_visible")
def test_visible_not_scribe_modality(mock_is_debug: MagicMock) -> None:
    mock_is_debug.return_value = False
    event = Event(EventRequest(context='{"user": {"id": "staff1"}}'))
    tested = ScribeAuditApp(event, {"Modality": "copilot", "ScribeDebugStaffers": "staff1"})
    assert tested.visible() is False


@patch("hyperscribe.scribe.application.audit_app.Note")
@patch("hyperscribe.scribe.application.audit_app.LaunchModalEffect")
def test_handle(launch_modal_effect: object, mock_note: MagicMock) -> None:
    launch_modal_effect.return_value.apply.side_effect = [  # type: ignore[union-attr]
        Effect(type="LOG", payload="SomePayload")
    ]
    launch_modal_effect.TargetType.NOTE = "note"  # type: ignore[union-attr]
    mock_qs = MagicMock(spec=QuerySet)
    mock_qs.get.return_value = "uuid-5481"
    mock_note.objects.values_list.return_value = mock_qs

    event = Event(EventRequest(context='{"note_id":5481}'))
    tested = ScribeAuditApp(event, {})
    result = tested.handle()

    assert result == [Effect(type="LOG", payload="SomePayload")]
    mock_qs.get.assert_called_once_with(dbid=5481)
    assert launch_modal_effect.mock_calls == [  # type: ignore[union-attr]
        call(
            url="/plugin-io/api/hyperscribe/scribe/app?note_id=uuid-5481&view=audit",
            target="note",
            title="Scribe Audit Log",
        ),
        call().apply(),
    ]
