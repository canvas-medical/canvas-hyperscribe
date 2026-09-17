import json
from unittest.mock import MagicMock, patch

from canvas_sdk.events import Event, EventType
from canvas_sdk.handlers.base import BaseHandler
from canvas_generated.messages.events_pb2 import Event as EventRequest

from hyperscribe.scribe.handlers.note_lock_guard import NoteLockGuard, _scribe_pending_finalization

MODULE = "hyperscribe.scribe.handlers.note_lock_guard"


def _make_event(state: str = "LKD", note_id: str = "note-uuid") -> Event:
    return Event(EventRequest(context=json.dumps({"state": state, "note_id": note_id})))


def _configure_models(
    mock_note: MagicMock,
    mock_summary: MagicMock,
    mock_transcript: MagicMock,
    *,
    note_dbid: int | None = 42,
    summary: dict | None = None,
    transcript_items: list | None = None,
) -> None:
    mock_note.objects.filter.return_value.values_list.return_value.first.return_value = note_dbid
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = summary
    mock_transcript.objects.filter.return_value.values_list.return_value.first.return_value = transcript_items


def test_class() -> None:
    assert issubclass(NoteLockGuard, BaseHandler)


def test_responds_to_pre_create() -> None:
    assert NoteLockGuard.RESPONDS_TO == [EventType.Name(EventType.NOTE_STATE_CHANGE_EVENT_PRE_CREATE)]


# --- compute: state filtering ---


@patch(f"{MODULE}.ScribeTranscript")
@patch(f"{MODULE}.ScribeSummary")
@patch(f"{MODULE}.Note")
def test_non_lock_state_is_ignored(mock_note: MagicMock, mock_summary: MagicMock, mock_transcript: MagicMock) -> None:
    for state in ("PSH", "ULK", "NEW", "DLT"):
        tested = NoteLockGuard(_make_event(state=state), {})
        assert tested.compute() == []
    # Never touched the models when the state is not a lock.
    mock_note.objects.filter.assert_not_called()


@patch(f"{MODULE}.ScribeTranscript")
@patch(f"{MODULE}.ScribeSummary")
@patch(f"{MODULE}.Note")
def test_note_not_found_is_ignored(mock_note: MagicMock, mock_summary: MagicMock, mock_transcript: MagicMock) -> None:
    _configure_models(mock_note, mock_summary, mock_transcript, note_dbid=None)
    tested = NoteLockGuard(_make_event(), {})
    assert tested.compute() == []


# --- compute: gate decisions ---


@patch(f"{MODULE}.ScribeTranscript")
@patch(f"{MODULE}.ScribeSummary")
@patch(f"{MODULE}.Note")
def test_never_used_allows_lock(mock_note: MagicMock, mock_summary: MagicMock, mock_transcript: MagicMock) -> None:
    _configure_models(mock_note, mock_summary, mock_transcript, summary=None, transcript_items=None)
    tested = NoteLockGuard(_make_event(), {})
    assert tested.compute() == []


@patch(f"{MODULE}.ScribeTranscript")
@patch(f"{MODULE}.ScribeSummary")
@patch(f"{MODULE}.Note")
def test_approved_summary_allows_lock(
    mock_note: MagicMock, mock_summary: MagicMock, mock_transcript: MagicMock
) -> None:
    # Approved short-circuits even with a recording present.
    _configure_models(
        mock_note,
        mock_summary,
        mock_transcript,
        summary={"approved": True, "commands": [], "note_data": {}},
        transcript_items=[{"text": "hi"}],
    )
    tested = NoteLockGuard(_make_event(), {})
    assert tested.compute() == []


@patch(f"{MODULE}.ScribeTranscript")
@patch(f"{MODULE}.ScribeSummary")
@patch(f"{MODULE}.Note")
def test_pending_summary_blocks_lock(mock_note: MagicMock, mock_summary: MagicMock, mock_transcript: MagicMock) -> None:
    _configure_models(
        mock_note,
        mock_summary,
        mock_transcript,
        summary={"approved": False, "commands": [{"section_key": "history_of_present_illness"}], "note_data": {}},
        transcript_items=None,
    )
    tested = NoteLockGuard(_make_event(), {})
    result = tested.compute()
    assert len(result) == 1
    payload = json.loads(result[0].payload)
    assert "click Approve" in payload["data"]["errors"][0]["message"]


@patch(f"{MODULE}.ScribeTranscript")
@patch(f"{MODULE}.ScribeSummary")
@patch(f"{MODULE}.Note")
def test_block_message_uses_tab_name_secret(
    mock_note: MagicMock, mock_summary: MagicMock, mock_transcript: MagicMock
) -> None:
    _configure_models(
        mock_note,
        mock_summary,
        mock_transcript,
        summary={"approved": False, "commands": [{"section_key": "physical_exam"}], "note_data": {}},
    )
    tested = NoteLockGuard(_make_event(), {"ScribeTabName": "Copilot"})
    result = tested.compute()
    message = json.loads(result[0].payload)["data"]["errors"][0]["message"]
    assert "Copilot" in message
    assert "Scribe." not in message


# --- _scribe_pending_finalization predicate ---


@patch(f"{MODULE}.ScribeTranscript")
@patch(f"{MODULE}.ScribeSummary")
def test_predicate_from_the_note_only_is_not_usage(mock_summary: MagicMock, mock_transcript: MagicMock) -> None:
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = {
        "approved": False,
        "commands": [{"section_key": "from_the_note"}, {"section_key": "from_the_note"}],
        "note_data": {},
    }
    mock_transcript.objects.filter.return_value.values_list.return_value.first.return_value = None
    assert _scribe_pending_finalization(42) is False


@patch(f"{MODULE}.ScribeTranscript")
@patch(f"{MODULE}.ScribeSummary")
def test_predicate_real_command_is_usage(mock_summary: MagicMock, mock_transcript: MagicMock) -> None:
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = {
        "approved": False,
        "commands": [{"section_key": "from_the_note"}, {"section_key": "assess"}],
        "note_data": {},
    }
    mock_transcript.objects.filter.return_value.values_list.return_value.first.return_value = None
    assert _scribe_pending_finalization(42) is True


@patch(f"{MODULE}.ScribeTranscript")
@patch(f"{MODULE}.ScribeSummary")
def test_predicate_note_section_text_is_usage(mock_summary: MagicMock, mock_transcript: MagicMock) -> None:
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = {
        "approved": False,
        "commands": [],
        "note_data": {"sections": [{"text": "  patient reports..."}]},
    }
    mock_transcript.objects.filter.return_value.values_list.return_value.first.return_value = None
    assert _scribe_pending_finalization(42) is True


@patch(f"{MODULE}.ScribeTranscript")
@patch(f"{MODULE}.ScribeSummary")
def test_predicate_blank_section_text_is_not_usage(mock_summary: MagicMock, mock_transcript: MagicMock) -> None:
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = {
        "approved": False,
        "commands": [],
        "note_data": {"sections": [{"text": "   \n  "}]},
    }
    mock_transcript.objects.filter.return_value.values_list.return_value.first.return_value = None
    assert _scribe_pending_finalization(42) is False


@patch(f"{MODULE}.ScribeTranscript")
@patch(f"{MODULE}.ScribeSummary")
def test_predicate_recording_without_summary_is_usage(mock_summary: MagicMock, mock_transcript: MagicMock) -> None:
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = None
    mock_transcript.objects.filter.return_value.values_list.return_value.first.return_value = [{"text": "hi"}]
    assert _scribe_pending_finalization(42) is True
