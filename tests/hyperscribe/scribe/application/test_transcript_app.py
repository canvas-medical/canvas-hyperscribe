from unittest.mock import MagicMock, call, patch

from django.db.models import QuerySet

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.handlers.application import NoteApplication

from hyperscribe.scribe.application.transcript_app import ScribeApp, _scribe_tab_has_content


def test_class() -> None:
    assert issubclass(ScribeApp, NoteApplication)


def test_constants() -> None:
    assert ScribeApp.IDENTIFIER == "hyperscribe__scribe"


def test_name_defaults_to_scribe() -> None:
    app = MagicMock(spec=ScribeApp)
    app.secrets = {}
    assert ScribeApp.NAME.fget(app) == "Scribe"


def test_name_from_secret() -> None:
    app = MagicMock(spec=ScribeApp)
    app.secrets = {"ScribeTabName": "Note"}
    assert ScribeApp.NAME.fget(app) == "Note"


@patch(
    "hyperscribe.scribe.application.transcript_app._staff_key_from_actor", side_effect=lambda e: str(e.actor.id or "")
)
@patch("hyperscribe.scribe.application.transcript_app.Settings")
def test_visible(mock_settings_cls: MagicMock, _mock_key: MagicMock) -> None:
    mock_settings = MagicMock()
    mock_settings_cls.from_dictionary.return_value = mock_settings

    # scribe modality for this staff → visible
    mock_settings.is_scribe_modality.return_value = True
    event = Event(EventRequest(actor="staff1"))
    tested = ScribeApp(event, {"Modality": "scribe"})
    assert tested.visible() is True
    mock_settings.is_scribe_modality.assert_called_with("staff1")

    # not scribe modality for this staff → not visible
    mock_settings.is_scribe_modality.return_value = False
    event = Event(EventRequest(actor="staff2"))
    tested = ScribeApp(event, {"Modality": "copilot"})
    assert tested.visible() is False
    mock_settings.is_scribe_modality.assert_called_with("staff2")


@patch(
    "hyperscribe.scribe.application.transcript_app._staff_key_from_actor", side_effect=lambda e: str(e.actor.id or "")
)
@patch("hyperscribe.scribe.application.transcript_app.Settings")
def test_visible_missing_user_context(mock_settings_cls: MagicMock, _mock_key: MagicMock) -> None:
    mock_settings = MagicMock()
    mock_settings_cls.from_dictionary.return_value = mock_settings
    mock_settings.is_scribe_modality.return_value = False

    event = Event(EventRequest(actor=""))
    tested = ScribeApp(event, {})
    assert tested.visible() is False
    mock_settings.is_scribe_modality.assert_called_with("")


@patch(
    "hyperscribe.scribe.application.transcript_app._staff_key_from_actor", side_effect=lambda e: str(e.actor.id or "")
)
@patch("hyperscribe.scribe.application.transcript_app.Note")
@patch("hyperscribe.scribe.application.transcript_app.Settings")
def test_visible_note_type_match(mock_settings_cls: MagicMock, mock_note: MagicMock, _mock_key: MagicMock) -> None:
    mock_settings = MagicMock()
    mock_settings_cls.from_dictionary.return_value = mock_settings
    mock_settings.is_scribe_modality.return_value = True

    mock_qs = MagicMock(spec=QuerySet)
    mock_qs.get.return_value = "Office Visit"
    mock_note.objects.values_list.return_value = mock_qs

    event = Event(EventRequest(actor="staff1", context='{"note_id": 123}'))
    tested = ScribeApp(event, {"ScribeNoteTypes": "Office Visit, Telehealth"})
    assert tested.visible() is True
    mock_qs.get.assert_called_once_with(dbid=123)


@patch(
    "hyperscribe.scribe.application.transcript_app._staff_key_from_actor", side_effect=lambda e: str(e.actor.id or "")
)
@patch("hyperscribe.scribe.application.transcript_app.Note")
@patch("hyperscribe.scribe.application.transcript_app.Settings")
def test_visible_note_type_no_match(mock_settings_cls: MagicMock, mock_note: MagicMock, _mock_key: MagicMock) -> None:
    mock_settings = MagicMock()
    mock_settings_cls.from_dictionary.return_value = mock_settings
    mock_settings.is_scribe_modality.return_value = True

    mock_qs = MagicMock(spec=QuerySet)
    mock_qs.get.return_value = "Phone Call"
    mock_note.objects.values_list.return_value = mock_qs

    event = Event(EventRequest(actor="staff1", context='{"note_id": 123}'))
    tested = ScribeApp(event, {"ScribeNoteTypes": "Office Visit, Telehealth"})
    assert tested.visible() is False


@patch(
    "hyperscribe.scribe.application.transcript_app._staff_key_from_actor", side_effect=lambda e: str(e.actor.id or "")
)
@patch("hyperscribe.scribe.application.transcript_app.Note")
@patch("hyperscribe.scribe.application.transcript_app.Settings")
def test_visible_note_type_case_insensitive(
    mock_settings_cls: MagicMock, mock_note: MagicMock, _mock_key: MagicMock
) -> None:
    mock_settings = MagicMock()
    mock_settings_cls.from_dictionary.return_value = mock_settings
    mock_settings.is_scribe_modality.return_value = True

    mock_qs = MagicMock(spec=QuerySet)
    mock_qs.get.return_value = "office visit"
    mock_note.objects.values_list.return_value = mock_qs

    event = Event(EventRequest(actor="staff1", context='{"note_id": 123}'))
    tested = ScribeApp(event, {"ScribeNoteTypes": "Office Visit"})
    assert tested.visible() is True


@patch(
    "hyperscribe.scribe.application.transcript_app._staff_key_from_actor", side_effect=lambda e: str(e.actor.id or "")
)
@patch("hyperscribe.scribe.application.transcript_app.Settings")
def test_visible_note_type_empty_secret_allows_all(mock_settings_cls: MagicMock, _mock_key: MagicMock) -> None:
    mock_settings = MagicMock()
    mock_settings_cls.from_dictionary.return_value = mock_settings
    mock_settings.is_scribe_modality.return_value = True

    event = Event(EventRequest(actor="staff1"))
    tested = ScribeApp(event, {"ScribeNoteTypes": ""})
    assert tested.visible() is True


@patch(
    "hyperscribe.scribe.application.transcript_app._staff_key_from_actor", side_effect=lambda e: str(e.actor.id or "")
)
@patch("hyperscribe.scribe.application.transcript_app.Settings")
def test_visible_note_type_missing_secret_allows_all(mock_settings_cls: MagicMock, _mock_key: MagicMock) -> None:
    mock_settings = MagicMock()
    mock_settings_cls.from_dictionary.return_value = mock_settings
    mock_settings.is_scribe_modality.return_value = True

    event = Event(EventRequest(actor="staff1"))
    tested = ScribeApp(event, {})
    assert tested.visible() is True


@patch(
    "hyperscribe.scribe.application.transcript_app._staff_key_from_actor", side_effect=lambda e: str(e.actor.id or "")
)
@patch("hyperscribe.scribe.application.transcript_app.Note")
@patch("hyperscribe.scribe.application.transcript_app.Settings")
def test_visible_note_type_note_not_found(
    mock_settings_cls: MagicMock, mock_note: MagicMock, _mock_key: MagicMock
) -> None:
    mock_settings = MagicMock()
    mock_settings_cls.from_dictionary.return_value = mock_settings
    mock_settings.is_scribe_modality.return_value = True

    from canvas_sdk.v1.data.note import Note as RealNote

    mock_qs = MagicMock(spec=QuerySet)
    mock_qs.get.side_effect = RealNote.DoesNotExist
    mock_note.objects.values_list.return_value = mock_qs
    mock_note.DoesNotExist = RealNote.DoesNotExist

    event = Event(EventRequest(actor="staff1", context='{"note_id": 999}'))
    tested = ScribeApp(event, {"ScribeNoteTypes": "Office Visit"})
    assert tested.visible() is False


@patch("hyperscribe.scribe.application.transcript_app.Note")
@patch("hyperscribe.scribe.application.transcript_app.LaunchModalEffect")
def test_handle(launch_modal_effect: object, mock_note: MagicMock) -> None:
    launch_modal_effect.return_value.apply.side_effect = [  # type: ignore[union-attr]
        Effect(type="LOG", payload="SomePayload")
    ]
    launch_modal_effect.TargetType.NOTE = "note"  # type: ignore[union-attr]
    mock_qs = MagicMock(spec=QuerySet)
    mock_qs.get.return_value = "uuid-5481"
    mock_note.objects.values_list.return_value = mock_qs

    event = Event(EventRequest(context='{"note_id":5481}'))
    tested = ScribeApp(event, {})
    result = tested.handle()

    assert result == [Effect(type="LOG", payload="SomePayload")]
    mock_qs.get.assert_called_once_with(dbid=5481)
    assert launch_modal_effect.mock_calls == [  # type: ignore[union-attr]
        call(
            url="/plugin-io/api/hyperscribe/scribe/app?note_id=uuid-5481&view=scribe",
            target="note",
            title="Scribe",
        ),
        call().apply(),
    ]


# --- _scribe_tab_has_content ---


def _stub_transcript(items: list | None) -> MagicMock:
    qs = MagicMock()
    qs.first.return_value = items
    chain = MagicMock()
    chain.values_list.return_value = qs
    transcript_cls = MagicMock()
    transcript_cls.objects.filter.return_value = chain
    return transcript_cls


def _stub_summary(row: dict | None) -> MagicMock:
    chain = MagicMock()
    chain.first.return_value = row
    values = MagicMock()
    values.values.return_value = chain
    summary_cls = MagicMock()
    summary_cls.objects.filter.return_value = values
    return summary_cls


@patch("hyperscribe.scribe.application.transcript_app.ScribeSummary")
@patch("hyperscribe.scribe.application.transcript_app.ScribeTranscript")
def test_scribe_tab_has_content_no_rows(mock_transcript: MagicMock, mock_summary: MagicMock) -> None:
    mock_transcript.objects.filter.return_value.values_list.return_value.first.return_value = None
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = None
    assert _scribe_tab_has_content(99) is False


@patch("hyperscribe.scribe.application.transcript_app.ScribeSummary")
@patch("hyperscribe.scribe.application.transcript_app.ScribeTranscript")
def test_scribe_tab_has_content_transcript_items(
    mock_transcript: MagicMock, mock_summary: MagicMock
) -> None:
    mock_transcript.objects.filter.return_value.values_list.return_value.first.return_value = [
        {"text": "Hello"}
    ]
    assert _scribe_tab_has_content(99) is True
    mock_summary.objects.filter.assert_not_called()


@patch("hyperscribe.scribe.application.transcript_app.ScribeSummary")
@patch("hyperscribe.scribe.application.transcript_app.ScribeTranscript")
def test_scribe_tab_has_content_summary_approved(
    mock_transcript: MagicMock, mock_summary: MagicMock
) -> None:
    mock_transcript.objects.filter.return_value.values_list.return_value.first.return_value = []
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = {
        "note_data": {},
        "commands": [],
        "approved": True,
    }
    assert _scribe_tab_has_content(99) is True


@patch("hyperscribe.scribe.application.transcript_app.ScribeSummary")
@patch("hyperscribe.scribe.application.transcript_app.ScribeTranscript")
def test_scribe_tab_has_content_summary_commands(
    mock_transcript: MagicMock, mock_summary: MagicMock
) -> None:
    mock_transcript.objects.filter.return_value.values_list.return_value.first.return_value = []
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = {
        "note_data": {},
        "commands": [{"command_type": "task", "display": ""}],
        "approved": False,
    }
    assert _scribe_tab_has_content(99) is True


@patch("hyperscribe.scribe.application.transcript_app.ScribeSummary")
@patch("hyperscribe.scribe.application.transcript_app.ScribeTranscript")
def test_scribe_tab_has_content_summary_text(
    mock_transcript: MagicMock, mock_summary: MagicMock
) -> None:
    mock_transcript.objects.filter.return_value.values_list.return_value.first.return_value = []
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = {
        "note_data": {"sections": [{"key": "cc", "title": "CC", "text": "Patient reports cough."}]},
        "commands": [],
        "approved": False,
    }
    assert _scribe_tab_has_content(99) is True


@patch("hyperscribe.scribe.application.transcript_app.ScribeSummary")
@patch("hyperscribe.scribe.application.transcript_app.ScribeTranscript")
def test_scribe_tab_has_content_summary_blank(
    mock_transcript: MagicMock, mock_summary: MagicMock
) -> None:
    """A ScribeSummary row exists from a manual-mode template flip, but the user
    typed nothing and never clicked Approve."""
    mock_transcript.objects.filter.return_value.values_list.return_value.first.return_value = []
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = {
        "note_data": {"sections": [{"key": "cc", "title": "CC", "text": ""}]},
        "commands": [],
        "approved": False,
    }
    assert _scribe_tab_has_content(99) is False


@patch("hyperscribe.scribe.application.transcript_app.ScribeSummary")
@patch("hyperscribe.scribe.application.transcript_app.ScribeTranscript")
def test_scribe_tab_has_content_whitespace_only(
    mock_transcript: MagicMock, mock_summary: MagicMock
) -> None:
    mock_transcript.objects.filter.return_value.values_list.return_value.first.return_value = []
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = {
        "note_data": {"sections": [{"key": "cc", "title": "CC", "text": "   \n  "}]},
        "commands": [],
        "approved": False,
    }
    assert _scribe_tab_has_content(99) is False


# --- ScribeApp.open_by_default ---


@patch("hyperscribe.scribe.application.transcript_app._scribe_tab_has_content")
@patch("hyperscribe.scribe.application.transcript_app.Helper.editable_note")
def test_open_by_default_editable_note(
    mock_editable: MagicMock, mock_has_content: MagicMock
) -> None:
    mock_editable.return_value = True
    mock_has_content.return_value = False  # irrelevant for editable
    event = Event(EventRequest(context='{"note_id": 7}'))
    tested = ScribeApp(event, {})
    assert tested.open_by_default() is True


@patch("hyperscribe.scribe.application.transcript_app._scribe_tab_has_content")
@patch("hyperscribe.scribe.application.transcript_app.Helper.editable_note")
def test_open_by_default_locked_with_content(
    mock_editable: MagicMock, mock_has_content: MagicMock
) -> None:
    mock_editable.return_value = False
    mock_has_content.return_value = True
    event = Event(EventRequest(context='{"note_id": 7}'))
    tested = ScribeApp(event, {})
    assert tested.open_by_default() is True


@patch("hyperscribe.scribe.application.transcript_app._scribe_tab_has_content")
@patch("hyperscribe.scribe.application.transcript_app.Helper.editable_note")
def test_open_by_default_locked_blank_defers_to_legacy(
    mock_editable: MagicMock, mock_has_content: MagicMock
) -> None:
    mock_editable.return_value = False
    mock_has_content.return_value = False
    event = Event(EventRequest(context='{"note_id": 7}'))
    tested = ScribeApp(event, {})
    assert tested.open_by_default() is False
    mock_has_content.assert_called_once_with(7)


def test_open_by_default_no_note_id() -> None:
    event = Event(EventRequest(context="{}"))
    tested = ScribeApp(event, {})
    assert tested.open_by_default() is True
