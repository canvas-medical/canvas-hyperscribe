import json
import re
from http import HTTPStatus
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.db.models import QuerySet

from canvas_sdk.effects.simple_api import JSONResponse
from canvas_sdk.handlers.simple_api import SimpleAPI, StaffSessionAuthMixin

from hyperscribe.scribe.api.session_view import (
    SUMMARY_STEPS,
    ScribeSessionView,
    _PROGRESS_CACHE_KEY_PREFIX,
    _match_conditions_to_sections,
)
from hyperscribe.scribe.backend import ScribeError
from hyperscribe.scribe.backend.models import (
    ClinicalNote,
    CodingEntry,
    CommandProposal,
    Condition,
    NormalizedData,
    NoteSection,
    Observation,
)

# Disable automatic route resolution
ScribeSessionView._ROUTES = {}


@pytest.fixture(autouse=True)
def _bypass_authorize_edit(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Default to authorized for the existing endpoint tests so they don't need
    to mock the Note/Helper.editable_note interaction the auth check performs.
    Tests that exercise the auth helper directly use a separate test file."""
    if request.node.get_closest_marker("no_authorize_bypass"):
        return
    from hyperscribe.scribe.api import session_view

    monkeypatch.setattr(session_view, "_authorize_edit", lambda *_args, **_kwargs: None)


def _helper_instance(staff_id: str = "staff-key-abc") -> ScribeSessionView:
    event = SimpleNamespace(context={"method": "GET"})
    secrets: dict[str, str] = {"ScribeBackend": '{"vendor": "nabla", "client_id": "id", "client_secret": "secret"}'}
    environment: dict[str, str] = {}
    view = ScribeSessionView(event, secrets, environment)
    view._path_pattern = re.compile(r".*")
    view.request = SimpleNamespace(
        headers={"canvas-logged-in-user-id": staff_id},
        query_params={},
        body=b"",
    )
    return view


def test_class() -> None:
    assert issubclass(ScribeSessionView, StaffSessionAuthMixin)
    assert issubclass(ScribeSessionView, SimpleAPI)


def test_constants() -> None:
    assert ScribeSessionView.PREFIX == "/scribe-session"


# --- /config ---


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_get_config_success(get_backend: MagicMock) -> None:
    mock_backend = MagicMock()
    mock_backend.get_transcription_config.return_value = {
        "vendor": "nabla",
        "ws_url": "wss://example.com/ws",
        "access_token": "tok",
        "sample_rate": 16000,
    }
    get_backend.return_value = mock_backend

    view = _helper_instance(staff_id="staff-key-abc")
    result = view.get_config()

    expected = [
        JSONResponse(
            {"vendor": "nabla", "ws_url": "wss://example.com/ws", "access_token": "tok", "sample_rate": 16000},
            status_code=HTTPStatus.OK,
        )
    ]
    assert result == expected
    mock_backend.get_transcription_config.assert_called_once_with(user_external_id="staff-key-abc")


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_get_config_unknown_vendor(get_backend: MagicMock) -> None:
    get_backend.side_effect = ScribeError("Unknown scribe vendor: 'bad'")

    view = _helper_instance()
    result = view.get_config()

    expected = [JSONResponse({"error": "Unknown scribe vendor: 'bad'"}, status_code=HTTPStatus.BAD_REQUEST)]
    assert result == expected


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_get_config_auth_error(get_backend: MagicMock) -> None:
    mock_backend = MagicMock()
    mock_backend.get_transcription_config.side_effect = ScribeError("Auth failed")
    get_backend.return_value = mock_backend

    view = _helper_instance()
    result = view.get_config()

    expected = [JSONResponse({"error": "Auth failed"}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
    assert result == expected


# --- /transcript ---


def _mock_cache() -> MagicMock:
    """Create a dict-backed mock cache for progress (still cached)."""
    store: dict[str, str] = {}
    cache = MagicMock()
    cache.set = lambda key, value, **kw: store.__setitem__(key, value)
    cache.get = lambda key, default=None: store.get(key, default)
    cache.delete = lambda key: store.pop(key, None)
    cache._store = store
    return cache


@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_get_transcript_success(mock_note: MagicMock, mock_transcript: MagicMock) -> None:
    mock_note.objects.values_list.return_value.get.return_value = 55
    items = [{"text": "Hello", "speaker": "patient", "start_offset_ms": 0, "end_offset_ms": 1000}]
    mock_transcript.objects.filter.return_value.values.return_value.first.return_value = {
        "items": items,
        "finalized": True,
    }

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "55"})
    result = view.get_transcript()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content) == {"items": items, "finalized": True, "started": True}


@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_get_transcript_empty(mock_note: MagicMock, mock_transcript: MagicMock) -> None:
    mock_note.objects.values_list.return_value.get.return_value = 999
    mock_transcript.objects.filter.return_value.values.return_value.first.return_value = None

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "999"})
    result = view.get_transcript()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content) == {"items": [], "finalized": False, "started": False}


def test_get_transcript_missing_note_id() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={})
    result = view.get_transcript()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST


# --- /save-transcript ---


@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_save_transcript_success(mock_note: MagicMock, mock_transcript: MagicMock) -> None:
    mock_note.objects.values_list.return_value.get.return_value = 42

    view = _helper_instance()
    items = [{"text": "Hello", "speaker": "patient", "start_offset_ms": 0, "end_offset_ms": 1000}]
    view.request = SimpleNamespace(
        headers={"canvas-logged-in-user-id": "staff-key-abc"},
        body=json.dumps({"note_id": "42", "transcript": {"items": items}}),
    )
    result = view.post_save_transcript()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content) == {"status": "ok"}
    mock_transcript.objects.update_or_create.assert_called_once_with(
        note_id=42, defaults={"items": items, "finalized": False, "provider_id": "staff-key-abc"}
    )


def test_save_transcript_missing_note_id() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"transcript": {"items": []}}))
    result = view.post_save_transcript()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "note_id" in json.loads(result[0].content)["error"]


def test_save_transcript_invalid_json() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body="not-json")
    result = view.post_save_transcript()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


# --- /summary ---


@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_get_summary_success(mock_note: MagicMock, mock_summary: MagicMock) -> None:
    mock_note.objects.values_list.return_value.get.return_value = 55
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = {
        "note_data": {"title": "SOAP", "sections": [{"key": "cc", "title": "CC", "text": "Pain"}]},
        "commands": [{"command_type": "rfv", "data": {"comment": "Pain"}}],
        "approved": True,
        "recommendations": [],
        "unmatched_conditions": [],
        "diagnosis_suggestions": {},
        "selected_template_name": "",
        "mode": "ai",
    }

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "55"})
    result = view.get_summary()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["note"]["title"] == "SOAP"
    assert data["commands"] == [{"command_type": "rfv", "data": {"comment": "Pain"}}]
    assert data["approved"] is True


@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_get_summary_empty(mock_note: MagicMock, mock_summary: MagicMock) -> None:
    mock_note.objects.values_list.return_value.get.return_value = 999
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = None

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "999"})
    result = view.get_summary()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content) == {"note": None, "commands": [], "approved": False}


def test_get_summary_missing_note_id() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={})
    result = view.get_summary()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST


# --- _load_summary mode self-heal ---


def _heal_summary_row(note_data: Any = None, commands: Any = None) -> dict[str, Any]:
    return {
        "note_data": note_data or {},
        "commands": commands or [],
        "approved": False,
        "recommendations": [],
        "unmatched_conditions": [],
        "diagnosis_suggestions": {},
        "selected_template_name": "",
        "mode": "",
    }


@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.ScribeAuditLog")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_get_summary_heals_blank_mode_from_start_ai(
    mock_note: MagicMock, mock_summary: MagicMock, mock_audit: MagicMock, mock_transcript: MagicMock
) -> None:
    mock_note.objects.values_list.return_value.get.return_value = 42
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = _heal_summary_row(
        note_data={"sections": [{"key": "hpi", "text": "Pain"}]}
    )
    mock_audit.objects.filter.return_value.values_list.return_value.first.return_value = [
        {"type": "START_AI", "ts": "2026-05-12T16:30:25Z"},
    ]

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "42"})
    result = view.get_summary()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content)["mode"] == "ai"
    mock_summary.objects.filter.assert_any_call(note_id=42, mode="")
    mock_summary.objects.filter.return_value.update.assert_called_once_with(mode="ai")
    mock_transcript.objects.filter.assert_not_called()


@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.ScribeAuditLog")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_get_summary_heals_blank_mode_from_start_manual(
    mock_note: MagicMock, mock_summary: MagicMock, mock_audit: MagicMock, mock_transcript: MagicMock
) -> None:
    mock_note.objects.values_list.return_value.get.return_value = 42
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = _heal_summary_row(
        commands=[{"command_type": "hpi"}]
    )
    mock_audit.objects.filter.return_value.values_list.return_value.first.return_value = [
        {"type": "START_MANUAL", "ts": "2026-05-12T16:30:25Z"},
    ]

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "42"})
    result = view.get_summary()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content)["mode"] == "manual"
    mock_summary.objects.filter.assert_any_call(note_id=42, mode="")
    mock_summary.objects.filter.return_value.update.assert_called_once_with(mode="manual")


@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.ScribeAuditLog")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_get_summary_last_start_wins_when_user_toggled(
    mock_note: MagicMock, mock_summary: MagicMock, mock_audit: MagicMock, mock_transcript: MagicMock
) -> None:
    mock_note.objects.values_list.return_value.get.return_value = 42
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = _heal_summary_row(
        commands=[{"command_type": "hpi"}]
    )
    mock_audit.objects.filter.return_value.values_list.return_value.first.return_value = [
        {"type": "START_AI", "ts": "2026-05-12T16:30:25Z"},
        {"type": "START_MANUAL", "ts": "2026-05-12T16:31:00Z"},
    ]

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "42"})
    result = view.get_summary()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content)["mode"] == "manual"
    mock_summary.objects.filter.assert_any_call(note_id=42, mode="")
    mock_summary.objects.filter.return_value.update.assert_called_once_with(mode="manual")


@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.ScribeAuditLog")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_get_summary_heals_to_ai_from_transcript_items(
    mock_note: MagicMock, mock_summary: MagicMock, mock_audit: MagicMock, mock_transcript: MagicMock
) -> None:
    mock_note.objects.values_list.return_value.get.return_value = 42
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = _heal_summary_row(
        note_data={"sections": [{"key": "hpi", "text": "Pain"}]}
    )
    mock_audit.objects.filter.return_value.values_list.return_value.first.return_value = []
    mock_transcript.objects.filter.return_value.values_list.return_value.first.return_value = [
        {"text": "I have a headache", "speaker": "patient"},
    ]

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "42"})
    result = view.get_summary()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content)["mode"] == "ai"
    mock_summary.objects.filter.assert_any_call(note_id=42, mode="")
    mock_summary.objects.filter.return_value.update.assert_called_once_with(mode="ai")


@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.ScribeAuditLog")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_get_summary_heals_to_manual_when_content_without_recording(
    mock_note: MagicMock, mock_summary: MagicMock, mock_audit: MagicMock, mock_transcript: MagicMock
) -> None:
    mock_note.objects.values_list.return_value.get.return_value = 42
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = _heal_summary_row(
        commands=[{"command_type": "hpi"}]
    )
    mock_audit.objects.filter.return_value.values_list.return_value.first.return_value = []
    mock_transcript.objects.filter.return_value.values_list.return_value.first.return_value = None

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "42"})
    result = view.get_summary()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content)["mode"] == "manual"
    mock_summary.objects.filter.assert_any_call(note_id=42, mode="")
    mock_summary.objects.filter.return_value.update.assert_called_once_with(mode="manual")


@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.ScribeAuditLog")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_get_summary_does_not_heal_truly_empty_row(
    mock_note: MagicMock, mock_summary: MagicMock, mock_audit: MagicMock, mock_transcript: MagicMock
) -> None:
    mock_note.objects.values_list.return_value.get.return_value = 42
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = _heal_summary_row()
    mock_audit.objects.filter.return_value.values_list.return_value.first.return_value = []
    mock_transcript.objects.filter.return_value.values_list.return_value.first.return_value = None

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "42"})
    result = view.get_summary()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content)["mode"] is None
    mock_summary.objects.filter.return_value.update.assert_not_called()


@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.ScribeAuditLog")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_get_summary_does_not_heal_template_only_session(
    mock_note: MagicMock, mock_summary: MagicMock, mock_audit: MagicMock, mock_transcript: MagicMock
) -> None:
    """A note where the user picked a template but never clicked Start AI /
    Start Manual must NOT be healed to 'manual'. Template-inserted commands
    aren't user-authored content, and healing to 'manual' would hide the
    Start buttons and disable the template dropdown — locking the user out."""
    mock_note.objects.values_list.return_value.get.return_value = 42
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = _heal_summary_row(
        commands=[
            {"command_type": "ros", "_template_inserted": True},
            {"command_type": "physical_exam", "_template_inserted": True},
        ],
    )
    mock_audit.objects.filter.return_value.values_list.return_value.first.return_value = [
        {"type": "SELECT_TEMPLATE", "details": {"name": "Subsequent Visit"}},
    ]
    mock_transcript.objects.filter.return_value.values_list.return_value.first.return_value = None

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "42"})
    result = view.get_summary()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content)["mode"] is None
    mock_summary.objects.filter.return_value.update.assert_not_called()


@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.ScribeAuditLog")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_get_summary_does_not_heal_when_start_ai_failed(
    mock_note: MagicMock, mock_summary: MagicMock, mock_audit: MagicMock, mock_transcript: MagicMock
) -> None:
    """When recording.startRecording() fails (mic permission denied, device
    error, transcription backend unreachable), summary.js logs
    [START_AI, START_AI_FAILED] and resets mode to null. The heal must treat
    START_*_FAILED as cancelling its preceding START_* — otherwise it would
    write mode='ai' to a session that never actually recorded, hiding the
    Start AI / Start Manual buttons and locking the user out."""
    mock_note.objects.values_list.return_value.get.return_value = 42
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = _heal_summary_row()
    mock_audit.objects.filter.return_value.values_list.return_value.first.return_value = [
        {"type": "SELECT_TEMPLATE"},
        {"type": "START_AI"},
        {"type": "START_AI_FAILED"},
    ]
    mock_transcript.objects.filter.return_value.values_list.return_value.first.return_value = None

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "42"})
    result = view.get_summary()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content)["mode"] is None
    mock_summary.objects.filter.return_value.update.assert_not_called()


@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.ScribeAuditLog")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_get_summary_heals_to_ai_when_user_retries_after_failed_start(
    mock_note: MagicMock, mock_summary: MagicMock, mock_audit: MagicMock, mock_transcript: MagicMock
) -> None:
    """A failed START_AI cancels itself, but a subsequent successful START_AI
    (user grants mic permission and retries) still heals to 'ai'."""
    mock_note.objects.values_list.return_value.get.return_value = 42
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = _heal_summary_row(
        note_data={"sections": [{"key": "hpi", "text": "Pain"}]},
    )
    mock_audit.objects.filter.return_value.values_list.return_value.first.return_value = [
        {"type": "START_AI"},
        {"type": "START_AI_FAILED"},
        {"type": "START_AI"},
    ]
    mock_transcript.objects.filter.return_value.values_list.return_value.first.return_value = None

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "42"})
    result = view.get_summary()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content)["mode"] == "ai"
    mock_summary.objects.filter.return_value.update.assert_called_once_with(mode="ai")


@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.ScribeAuditLog")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_get_summary_no_ops_response_when_cas_loses_to_concurrent_save(
    mock_note: MagicMock, mock_summary: MagicMock, mock_audit: MagicMock, mock_transcript: MagicMock
) -> None:
    """If a concurrent /save-summary commits a real mode between this
    request's stale read and the heal write, the CAS UPDATE matches 0 rows.
    The response must not claim the inferred mode — it would contradict
    what's now persisted in the DB."""
    mock_note.objects.values_list.return_value.get.return_value = 42
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = _heal_summary_row(
        note_data={"sections": [{"key": "hpi", "text": "Pain"}]},
    )
    mock_audit.objects.filter.return_value.values_list.return_value.first.return_value = [
        {"type": "START_AI"},
    ]
    mock_summary.objects.filter.return_value.update.return_value = 0

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "42"})
    result = view.get_summary()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content)["mode"] is None
    mock_summary.objects.filter.return_value.update.assert_called_once_with(mode="ai")


# --- /save-summary ---


@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_save_summary_success(mock_note: MagicMock, mock_summary: MagicMock) -> None:
    mock_note.objects.values_list.return_value.get.return_value = 42

    view = _helper_instance()
    note = {"title": "SOAP", "sections": []}
    commands = [{"command_type": "hpi", "data": {"narrative": "Pain"}}]
    view.request = SimpleNamespace(
        body=json.dumps({"note_id": "42", "note": note, "commands": commands, "approved": True})
    )
    result = view.post_save_summary()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content) == {"status": "ok"}
    mock_summary.objects.update_or_create.assert_called_once()
    call_kwargs = mock_summary.objects.update_or_create.call_args
    assert call_kwargs.kwargs["note_id"] == 42
    assert call_kwargs.kwargs["defaults"]["note_data"] == note
    assert call_kwargs.kwargs["defaults"]["commands"] == commands
    assert call_kwargs.kwargs["defaults"]["approved"] is True


def test_save_summary_missing_note_id() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note": {}, "commands": []}))
    result = view.post_save_summary()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "note_id" in json.loads(result[0].content)["error"]


def test_save_summary_invalid_json() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body="not-json")
    result = view.post_save_summary()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_save_summary_defaults(mock_note: MagicMock, mock_summary: MagicMock) -> None:
    """When approved is not provided, it defaults to False."""
    mock_note.objects.values_list.return_value.get.return_value = 10

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note_id": "10", "note": {}, "commands": []}))
    result = view.post_save_summary()

    assert result[0].status_code == HTTPStatus.OK
    call_kwargs = mock_summary.objects.update_or_create.call_args
    assert call_kwargs.kwargs["defaults"]["approved"] is False


@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_save_summary_omits_mode_and_template_when_absent(mock_note: MagicMock, mock_summary: MagicMock) -> None:
    """Autosave paths that don't send mode / selected_template_name must not
    overwrite those columns — update_or_create only touches keys present in
    defaults, so omitting them preserves the existing DB values."""
    mock_note.objects.values_list.return_value.get.return_value = 42

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note_id": "42", "note": {}, "commands": [], "approved": False}))
    result = view.post_save_summary()

    assert result[0].status_code == HTTPStatus.OK
    defaults = mock_summary.objects.update_or_create.call_args.kwargs["defaults"]
    assert "mode" not in defaults
    assert "selected_template_name" not in defaults


@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_save_summary_clears_template_when_explicitly_null(mock_note: MagicMock, mock_summary: MagicMock) -> None:
    """Deselecting the visit template sends `selected_template_name: null`,
    which must clear the DB column (write '') rather than be silently dropped."""
    mock_note.objects.values_list.return_value.get.return_value = 42

    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note_id": "42",
                "note": {},
                "commands": [],
                "approved": False,
                "selected_template_name": None,
            }
        )
    )
    result = view.post_save_summary()

    assert result[0].status_code == HTTPStatus.OK
    defaults = mock_summary.objects.update_or_create.call_args.kwargs["defaults"]
    assert defaults["selected_template_name"] == ""


@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_save_summary_clears_mode_when_explicitly_null(mock_note: MagicMock, mock_summary: MagicMock) -> None:
    """Symmetric to template deselect: explicit `mode: null` clears the column."""
    mock_note.objects.values_list.return_value.get.return_value = 42

    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps({"note_id": "42", "note": {}, "commands": [], "approved": False, "mode": None})
    )
    result = view.post_save_summary()

    assert result[0].status_code == HTTPStatus.OK
    defaults = mock_summary.objects.update_or_create.call_args.kwargs["defaults"]
    assert defaults["mode"] == ""


# --- /generate-note ---


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_note_success(get_backend: MagicMock) -> None:
    mock_backend = MagicMock()
    mock_backend.generate_note.return_value = ClinicalNote(
        title="SOAP Note",
        sections=[NoteSection(key="subjective", title="Subjective", text="Headache.")],
    )
    get_backend.return_value = mock_backend

    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "transcript": {
                    "items": [
                        {"text": "I have a headache", "speaker": "patient", "start_offset_ms": 0, "end_offset_ms": 2000}
                    ]
                }
            }
        )
    )
    result = view.post_generate_note()

    expected = [
        JSONResponse(
            {
                "title": "SOAP Note",
                "sections": [{"key": "subjective", "title": "Subjective", "text": "Headache."}],
            },
            status_code=HTTPStatus.OK,
        )
    ]
    assert result == expected
    mock_backend.generate_note.assert_called_once()


@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.Note")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_note_from_cache(get_backend: MagicMock, mock_note: MagicMock, mock_transcript: MagicMock) -> None:
    mock_note.objects.values_list.return_value.get.return_value = 99
    cached_items = [{"text": "I feel dizzy", "speaker": "patient", "start_offset_ms": 0, "end_offset_ms": 1500}]
    mock_transcript.objects.filter.return_value.values.return_value.first.return_value = {
        "items": cached_items,
        "finalized": True,
    }

    mock_backend = MagicMock()
    mock_backend.generate_note.return_value = ClinicalNote(
        title="SOAP Note",
        sections=[NoteSection(key="subjective", title="Subjective", text="Dizzy.")],
    )
    get_backend.return_value = mock_backend

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note_id": "99"}))
    result = view.post_generate_note()

    assert result[0].status_code == HTTPStatus.OK
    mock_backend.generate_note.assert_called_once()
    transcript_arg = mock_backend.generate_note.call_args.args[0]
    assert len(transcript_arg.items) == 1
    assert transcript_arg.items[0].text == "I feel dizzy"


@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.Note")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_note_no_transcript_no_cache(
    get_backend: MagicMock, mock_note: MagicMock, mock_transcript: MagicMock
) -> None:
    mock_note.objects.values_list.return_value.get.return_value = 999
    mock_transcript.objects.filter.return_value.values.return_value.first.return_value = None
    get_backend.return_value = MagicMock()

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note_id": "999"}))
    result = view.post_generate_note()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "No transcript" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.Note")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_note_rejects_non_finalized_transcript(
    get_backend: MagicMock, mock_note: MagicMock, mock_transcript: MagicMock
) -> None:
    mock_note.objects.values_list.return_value.get.return_value = 42
    mock_transcript.objects.filter.return_value.values.return_value.first.return_value = {
        "items": [{"text": "hi", "speaker": "patient"}],
        "finalized": False,
    }
    get_backend.return_value = MagicMock()

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note_id": "42"}))
    result = view.post_generate_note()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "still in progress" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_note_with_patient_context(get_backend: MagicMock) -> None:
    mock_backend = MagicMock()
    mock_backend.generate_note.return_value = ClinicalNote(title="Note", sections=[])
    get_backend.return_value = mock_backend

    view = _helper_instance()
    item = {"text": "hi", "speaker": "patient", "start_offset_ms": 0, "end_offset_ms": 500}
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "transcript": {"items": [item]},
                "patient_context": {
                    "name": "Jane Doe",
                    "birth_date": "1990-01-01",
                    "gender": "female",
                    "encounter_diagnoses": [{"system": "ICD-10", "code": "R51", "display": "Headache"}],
                },
            }
        )
    )
    result = view.post_generate_note()

    assert result[0].status_code == HTTPStatus.OK
    call_kwargs = mock_backend.generate_note.call_args
    patient_ctx = call_kwargs.kwargs["patient_context"]
    assert patient_ctx.name == "Jane Doe"
    assert patient_ctx.encounter_diagnoses[0].code == "R51"


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_note_invalid_json(get_backend: MagicMock) -> None:
    get_backend.return_value = MagicMock()

    view = _helper_instance()
    view.request = SimpleNamespace(body="not-json")
    result = view.post_generate_note()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_note_backend_error(get_backend: MagicMock) -> None:
    mock_backend = MagicMock()
    mock_backend.generate_note.side_effect = ScribeError("Note generation failed")
    get_backend.return_value = mock_backend

    view = _helper_instance()
    item = {"text": "hi", "speaker": "patient", "start_offset_ms": 0, "end_offset_ms": 500}
    view.request = SimpleNamespace(body=json.dumps({"transcript": {"items": [item]}}))
    result = view.post_generate_note()

    expected = [JSONResponse({"error": "Note generation failed"}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
    assert result == expected


# --- /generate-normalized-data ---


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_normalized_data_success(get_backend: MagicMock) -> None:
    mock_backend = MagicMock()
    mock_backend.generate_normalized_data.return_value = NormalizedData(
        conditions=[
            Condition(
                display="Headache",
                clinical_status="active",
                coding=[CodingEntry(system="ICD-10", code="R51", display="Headache")],
            )
        ],
        observations=[
            Observation(
                display="BP",
                value="120/80",
                unit="mmHg",
                coding=[CodingEntry(system="LOINC", code="85354-9", display="Blood pressure")],
            )
        ],
    )
    get_backend.return_value = mock_backend

    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note": {
                    "title": "SOAP Note",
                    "sections": [{"key": "subjective", "title": "Subjective", "text": "Headache."}],
                }
            }
        )
    )
    result = view.post_generate_normalized_data()

    assert result[0].status_code == HTTPStatus.OK
    response_data = json.loads(result[0].content)
    assert len(response_data["conditions"]) == 1
    assert response_data["conditions"][0]["display"] == "Headache"
    assert response_data["conditions"][0]["coding"][0]["code"] == "R51"
    assert len(response_data["observations"]) == 1
    assert response_data["observations"][0]["value"] == "120/80"
    # section_conditions: "subjective" mentions "Headache"
    assert "section_conditions" in response_data
    assert "subjective" in response_data["section_conditions"]
    assert response_data["section_conditions"]["subjective"][0]["display"] == "Headache"


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_normalized_data_invalid_json(get_backend: MagicMock) -> None:
    get_backend.return_value = MagicMock()

    view = _helper_instance()
    view.request = SimpleNamespace(body="bad-json")
    result = view.post_generate_normalized_data()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_normalized_data_backend_error(get_backend: MagicMock) -> None:
    mock_backend = MagicMock()
    mock_backend.generate_normalized_data.side_effect = ScribeError("Normalization failed")
    get_backend.return_value = mock_backend

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note": {"title": "Note", "sections": []}}))
    result = view.post_generate_normalized_data()

    expected = [JSONResponse({"error": "Normalization failed"}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
    assert result == expected


# --- _match_conditions_to_sections ---


def test_match_conditions_assessment_plan_gets_all() -> None:
    """Assessment/plan sections receive all conditions regardless of text."""
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="assessment_and_plan", title="A&P", text="Manage conditions."),
            NoteSection(key="plan", title="Plan", text="Follow up."),
        ],
    )
    headache_coding = [CodingEntry(system="ICD-10", code="R51", display="Headache")]
    htn_coding = [CodingEntry(system="ICD-10", code="I10", display="Essential hypertension")]
    conditions = [
        Condition(display="Headache", clinical_status="active", coding=headache_coding),
        Condition(display="Hypertension", clinical_status="active", coding=htn_coding),
    ]
    result = _match_conditions_to_sections(note, conditions)
    assert len(result["assessment_and_plan"]) == 2
    assert len(result["plan"]) == 2


def test_match_conditions_text_match() -> None:
    """Non-plan sections only get conditions whose display matches the text."""
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="history_of_present_illness", title="HPI", text="Patient reports a headache for 3 days."),
        ],
    )
    headache_coding = [CodingEntry(system="ICD-10", code="R51", display="Headache")]
    htn_coding = [CodingEntry(system="ICD-10", code="I10", display="Essential hypertension")]
    conditions = [
        Condition(display="Headache", clinical_status="active", coding=headache_coding),
        Condition(display="Hypertension", clinical_status="active", coding=htn_coding),
    ]
    result = _match_conditions_to_sections(note, conditions)
    assert len(result["history_of_present_illness"]) == 1
    assert result["history_of_present_illness"][0]["display"] == "Headache"
    assert result["history_of_present_illness"][0]["coding"][0]["code"] == "R51"


def test_match_conditions_case_insensitive() -> None:
    """Matching is case-insensitive."""
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="subjective", title="Subjective", text="SEVERE HEADACHE reported.")],
    )
    conditions = [
        Condition(display="headache", clinical_status="active", coding=[]),
    ]
    result = _match_conditions_to_sections(note, conditions)
    assert "subjective" in result
    assert result["subjective"][0]["display"] == "headache"


def test_match_conditions_empty_section_text() -> None:
    """Sections with empty text produce no entries (unless assessment/plan)."""
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="review_of_systems", title="ROS", text="")],
    )
    conditions = [
        Condition(display="Headache", clinical_status="active", coding=[]),
    ]
    result = _match_conditions_to_sections(note, conditions)
    assert "review_of_systems" not in result


def test_match_conditions_no_conditions() -> None:
    """When there are no conditions, all sections produce empty result."""
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="assessment_and_plan", title="A&P", text="Plan here."),
            NoteSection(key="subjective", title="Subjective", text="Pain."),
        ],
    )
    result = _match_conditions_to_sections(note, [])
    assert result == {}


# --- /extract-commands ---


def test_extract_commands_success() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note": {
                    "title": "Note",
                    "sections": [
                        {"key": "chief_complaint", "title": "Chief Complaint", "text": "Back pain for 3 weeks."},
                        {"key": "history_of_present_illness", "title": "HPI", "text": "Radiates to left leg."},
                        {"key": "vitals", "title": "Vitals", "text": "BP 120/80, HR 72"},
                        {"key": "plan", "title": "Plan", "text": "Start naproxen. Order MRI."},
                    ],
                }
            }
        )
    )
    result = view.post_extract_commands()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    commands = data["commands"]
    types = [c["command_type"] for c in commands]
    assert types == ["rfv", "hpi", "vitals", "plan"]
    assert commands[0]["data"]["comment"] == "Back pain for 3 weeks."
    assert commands[0]["section_key"] == "chief_complaint"
    assert commands[1]["data"]["narrative"] == "Radiates to left leg."
    assert commands[1]["section_key"] == "history_of_present_illness"
    assert commands[2]["data"]["blood_pressure_systole"] == 120
    assert commands[2]["data"]["pulse"] == 72
    assert commands[2]["section_key"] == "vitals"
    assert commands[3]["data"]["narrative"] == "Start naproxen. Order MRI."
    assert commands[3]["section_key"] == "plan"
    assert all(c["selected"] is True for c in commands)
    assert all(c["already_documented"] is False for c in commands)


def test_extract_commands_empty_note() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note": {"title": "Empty", "sections": []}}))
    result = view.post_extract_commands()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["commands"] == []


def test_extract_commands_invalid_json() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body="not-json")
    result = view.post_extract_commands()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


# --- /insert-commands ---


@patch("hyperscribe.scribe.api.session_view.build_effects")
def test_insert_commands_success(mock_build: MagicMock) -> None:
    mock_effect_1 = MagicMock()
    mock_effect_2 = MagicMock()
    attempted = [
        {"command_uuid": "u1", "command_type": "hpi", "display": "Back pain"},
        {"command_uuid": "u2", "command_type": "plan", "display": "Start naproxen"},
    ]
    mock_build.return_value = ([mock_effect_1, mock_effect_2], [], attempted, [])

    view = _helper_instance()
    commands = [
        {"command_type": "hpi", "data": {"narrative": "Back pain"}},
        {"command_type": "plan", "data": {"narrative": "Start naproxen"}},
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    result = view.post_insert_commands()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["inserted"] == 2
    assert data["metadata_pending"] == []
    assert len(data["attempted"]) == 2
    assert len(result) == 3  # JSONResponse + 2 effects
    assert result[1] is mock_effect_1
    assert result[2] is mock_effect_2
    mock_build.assert_called_once_with(commands, "note-uuid-123", {"AlertFacilityEnabled": False})


@patch("hyperscribe.scribe.api.session_view.build_effects")
@patch("hyperscribe.scribe.api.session_view.prefill_assess_backgrounds")
def test_insert_commands_calls_prefill_assess_backgrounds_before_build(
    mock_prefill: MagicMock, mock_build: MagicMock
) -> None:
    """The endpoint must invoke ``prefill_assess_backgrounds`` before
    ``build_effects`` so the assess proposal's ``background`` is populated
    by the time the SDK command is constructed.

    This pins the new symmetric placement (parallel to ``annotate_duplicates``)
    — without it, a refactor could delete the callsite and every other
    insert_commands test would still pass (the helper short-circuits on bad
    UUIDs and never raises).
    """
    mock_build.return_value = ([], [], [], [])

    view = _helper_instance()
    commands = [
        {"command_type": "assess", "data": {"condition_id": "cond-1", "narrative": "Stable"}},
    ]
    view.request = SimpleNamespace(
        body=json.dumps({"note_uuid": "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0", "commands": commands})
    )
    view.post_insert_commands()

    # The view re-parses the JSON, so the list it passes is NOT the same object
    # as the ``commands`` we constructed here — assert on shape, not identity.
    prefill_call_commands = mock_prefill.call_args.args[0]
    assert prefill_call_commands == commands
    assert mock_prefill.call_args.args[1] == "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0"
    # Order: prefill must run BEFORE build_effects, and BOTH must see the SAME
    # in-memory list so the mutation lands. Compare identity between the two
    # call arg lists (the view's own ``commands`` local).
    build_call_commands = mock_build.call_args.args[0]
    assert prefill_call_commands is build_call_commands, (
        "prefill_assess_backgrounds and build_effects must share the same commands "
        "list so the in-place mutation by prefill is visible to build"
    )


@patch("hyperscribe.scribe.api.session_view.build_effects")
def test_insert_commands_with_metadata_pending(mock_build: MagicMock) -> None:
    mock_effect = MagicMock()
    pending = [
        {
            "command_uuid": "uuid-1",
            "command_type": "medication_statement",
            "note_uuid": "note-uuid",
            "metadata": {"alert_facility": "true"},
        },
    ]
    mock_build.return_value = (
        [mock_effect],
        pending,
        [{"command_uuid": "uuid-1", "command_type": "medication_statement", "display": "Test"}],
        [],
    )

    view = _helper_instance()
    commands = [{"command_type": "medication_statement", "data": {"medication_text": "Test", "alert_facility": True}}]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    result = view.post_insert_commands()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["inserted"] == 1
    assert len(data["metadata_pending"]) == 1
    assert data["metadata_pending"][0]["command_uuid"] == "uuid-1"


@patch("hyperscribe.scribe.api.session_view.build_effects")
def test_insert_commands_empty(mock_build: MagicMock) -> None:
    mock_build.return_value = ([], [], [], [])

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": []}))
    result = view.post_insert_commands()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["inserted"] == 0
    assert data["metadata_pending"] == []
    assert len(result) == 1


def test_insert_commands_missing_note_uuid() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"commands": []}))
    result = view.post_insert_commands()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "note_uuid" in json.loads(result[0].content)["error"]


def test_insert_commands_invalid_json() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body="not-json")
    result = view.post_insert_commands()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.api.session_view.audit_event")
def test_insert_commands_build_validation_error_returns_400(mock_audit: MagicMock) -> None:
    """Regression for KOALA-5476: pydantic ValidationError during build() returns 400 with
    a structured ``validation_errors`` payload rather than crashing the whole batch with a 500.

    Per UAT feedback on PR #273, the response surfaces a friendly command-name label
    in ``display`` and a plain-English error sentence in ``errors`` (no raw input
    dictionary, no Pydantic-internal wording)."""
    view = _helper_instance()
    commands = [
        {"command_type": "vitals", "data": {"pulse": 8}, "display": "HR 8"},
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    result = view.post_insert_commands()

    assert len(result) == 1
    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    body = json.loads(result[0].content)
    assert body["error"] == "Validation failed"
    assert len(body["validation_errors"]) == 1
    err = body["validation_errors"][0]
    assert err["command_type"] == "vitals"
    assert err["display"] == "Vitals"
    assert err["errors"] == ["pulse must be greater than or equal to 30 (currently 8)"]
    mock_audit.assert_called_once()
    assert mock_audit.call_args.args[1] == "VALIDATION_FAILED"


# --- /insert-metadata ---


@patch("hyperscribe.scribe.api.session_view.build_metadata_effects")
def test_insert_metadata_success(mock_meta: MagicMock) -> None:
    mock_effect = MagicMock()
    mock_meta.return_value = [mock_effect]

    view = _helper_instance()
    pending = [
        {
            "command_uuid": "uuid-1",
            "command_type": "medication_statement",
            "note_uuid": "note-uuid",
            "metadata": {"alert_facility": "true"},
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid", "pending": pending}))
    result = view.post_insert_metadata()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["ok"] is True
    assert data["metadata_count"] == 1
    assert len(result) == 2
    mock_meta.assert_called_once_with(pending)


def test_insert_metadata_empty_pending() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid", "pending": []}))
    result = view.post_insert_metadata()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["ok"] is True


def test_insert_metadata_invalid_json() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body="not-json")
    result = view.post_insert_metadata()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


# --- sign-note ---


@patch("hyperscribe.scribe.api.session_view.NoteEffect")
@patch("hyperscribe.scribe.api.session_view.audit_event")
def test_sign_note_success(mock_audit: MagicMock, mock_note_cls: MagicMock) -> None:
    mock_note = MagicMock()
    mock_note.lock.return_value = "lock_effect"
    mock_note.sign.return_value = "sign_effect"
    mock_note_cls.return_value = mock_note

    view = _helper_instance()
    note_uuid = "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0"
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": note_uuid}))
    result = view.post_sign_note()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content)["ok"] is True
    assert result[1] == "lock_effect"
    assert result[2] == "sign_effect"
    assert len(result) == 3
    mock_note_cls.assert_called_once_with(instance_id=note_uuid)
    mock_note.lock.assert_called_once()
    mock_note.sign.assert_called_once()
    mock_audit.assert_called_once_with(note_uuid, "SIGN_NOTE", {})


def test_sign_note_missing_note_uuid() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({}))
    result = view.post_sign_note()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "note_uuid" in json.loads(result[0].content)["error"]


def test_sign_note_invalid_json() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body="not-json")
    result = view.post_sign_note()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


# --- annotate_duplicates delegation ---


@patch("hyperscribe.scribe.api.session_view.annotate_duplicates")
def test_extract_commands_with_note_uuid_triggers_annotation(mock_annotate: MagicMock) -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note": {
                    "title": "Note",
                    "sections": [{"key": "chief_complaint", "title": "CC", "text": "Pain."}],
                },
                "note_uuid": "note-uuid-123",
            }
        )
    )
    view.post_extract_commands()
    mock_annotate.assert_called_once()
    assert mock_annotate.call_args.args[1] == "note-uuid-123"


@patch("hyperscribe.scribe.api.session_view.annotate_duplicates")
def test_extract_commands_without_note_uuid_calls_annotate_with_empty(mock_annotate: MagicMock) -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note": {
                    "title": "Note",
                    "sections": [{"key": "chief_complaint", "title": "CC", "text": "Pain."}],
                },
            }
        )
    )
    view.post_extract_commands()
    mock_annotate.assert_called_once()
    assert mock_annotate.call_args.args[1] == ""


# --- prefill_assess_backgrounds delegation (carry-forward in UI proposal paths) ---


@patch("hyperscribe.scribe.api.session_view.annotate_duplicates")
@patch("hyperscribe.scribe.api.session_view.prefill_assess_backgrounds_for_proposals")
def test_extract_commands_calls_prefill_assess_backgrounds(mock_prefill: MagicMock, _mock_annotate: MagicMock) -> None:
    """The ``/extract-commands`` endpoint must invoke
    ``prefill_assess_backgrounds_for_proposals`` so the UI sees prior signed-note
    backgrounds pre-filled on the assess proposal BEFORE the provider opens the
    edit view. This is the primary site that fixes KOALA-5598 — without it, the
    textarea is empty at proposal time and any edit the provider makes wins over
    the carry-forward applied later at Approve time.

    ``annotate_duplicates`` is patched only to prevent its real DB query from
    firing in the unit test environment (it doesn't need to participate in the
    assertion).
    """
    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note": {
                    "title": "Note",
                    "sections": [{"key": "chief_complaint", "title": "CC", "text": "Pain."}],
                },
                "note_uuid": "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0",
            }
        )
    )
    view.post_extract_commands()
    mock_prefill.assert_called_once()
    assert mock_prefill.call_args.args[1] == "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0"


@patch("hyperscribe.scribe.contacts.resolve_zip_codes", return_value=[])
@patch("hyperscribe.scribe.api.session_view.annotate_duplicates")
@patch("hyperscribe.scribe.api.session_view.prefill_assess_backgrounds_for_proposals")
@patch("hyperscribe.scribe.api.session_view.recommend_commands")
def test_recommend_commands_calls_prefill_assess_backgrounds(
    mock_recommend: MagicMock,
    mock_prefill: MagicMock,
    _mock_annotate: MagicMock,
    _mock_zip: MagicMock,
) -> None:
    """The ``/recommend-commands`` endpoint must invoke
    ``prefill_assess_backgrounds_for_proposals`` on recommended proposals so
    background carry-forward applies symmetrically to AI-recommended assess
    commands, not just extracted ones.
    """
    mock_recommend.return_value = [
        CommandProposal(
            command_type="assess",
            display="Hypertension",
            data={"condition_id": "cond-1", "narrative": ""},
            section_key="_recommended",
        ),
    ]

    view = _helper_instance()
    view.secrets["AnthropicAPIKey"] = "test-key"
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note": {"title": "Note", "sections": []},
                "note_uuid": "5899e7bf-5ecb-4399-aceb-0e233bd4a8f1",
            }
        )
    )
    view.post_recommend_commands()
    mock_prefill.assert_called_once()
    assert mock_prefill.call_args.args[1] == "5899e7bf-5ecb-4399-aceb-0e233bd4a8f1"


# --- /search-medications ---


@patch("hyperscribe.scribe.api.session_view.CanvasScience.medication_details")
def test_search_medications_success(mock_details: MagicMock) -> None:
    from hyperscribe.structures.medication_detail import MedicationDetail

    mock_details.return_value = [
        MedicationDetail(fdb_code="12345", description="Lisinopril 10mg Tablet", quantities=[]),
        MedicationDetail(fdb_code="67890", description="Lisinopril 20mg Tablet", quantities=[]),
    ]
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"query": "Lisinopril"})
    result = view.get_search_medications()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert len(data["results"]) == 2
    assert data["results"][0]["fdb_code"] == "12345"
    assert data["results"][0]["description"] == "Lisinopril 10mg Tablet"
    assert data["results"][0]["quantities"] == []
    mock_details.assert_called_once_with(["Lisinopril"])


@patch("hyperscribe.scribe.api.session_view.CanvasScience.medication_details")
def test_search_medications_no_results(mock_details: MagicMock) -> None:
    mock_details.return_value = []
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"query": "xyznonexistent"})
    result = view.get_search_medications()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["results"] == []


def test_search_medications_empty_query() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"query": ""})
    result = view.get_search_medications()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["results"] == []


def test_search_medications_missing_query() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={})
    result = view.get_search_medications()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["results"] == []


# --- /search-allergies ---


@patch("hyperscribe.scribe.api.session_view.CanvasScience.search_allergy")
def test_search_allergies_success(mock_search: MagicMock) -> None:
    from hyperscribe.structures.allergy_detail import AllergyDetail

    mock_search.return_value = [
        AllergyDetail(
            concept_id_value=100,
            concept_id_description="Penicillin",
            concept_type="Allergen Group",
            concept_id_type=1,
        ),
        AllergyDetail(
            concept_id_value=200,
            concept_id_description="Amoxicillin",
            concept_type="Medication",
            concept_id_type=2,
        ),
    ]
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"query": "penicillin"})
    result = view.get_search_allergies()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert len(data["results"]) == 2
    assert data["results"][0]["concept_id"] == 100
    assert data["results"][0]["description"] == "Penicillin"
    assert data["results"][0]["concept_id_type"] == 1
    assert data["results"][1]["concept_id"] == 200
    mock_search.assert_called_once()


@patch("hyperscribe.scribe.api.session_view.CanvasScience.search_allergy")
def test_search_allergies_no_results(mock_search: MagicMock) -> None:
    mock_search.return_value = []
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"query": "xyznonexistent"})
    result = view.get_search_allergies()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["results"] == []


def test_search_allergies_empty_query() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"query": ""})
    result = view.get_search_allergies()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["results"] == []


def test_search_allergies_missing_query() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={})
    result = view.get_search_allergies()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["results"] == []


# --- /assignees ---


@patch("hyperscribe.scribe.api.session_view.Team")
@patch("hyperscribe.scribe.api.session_view.Staff")
def test_get_assignees_success(mock_staff_cls: MagicMock, mock_team_cls: MagicMock) -> None:
    staff_qs = MagicMock(spec=QuerySet)
    staff_qs.order_by.return_value = MagicMock(spec=QuerySet)
    staff_qs.order_by.return_value.values.return_value = [
        {"dbid": 1, "first_name": "Jane", "last_name": "Doe"},
        {"dbid": 2, "first_name": "John", "last_name": "Smith"},
    ]
    mock_staff_cls.objects.filter.return_value = staff_qs

    team_qs = MagicMock(spec=QuerySet)
    team_qs.order_by.return_value = MagicMock(spec=QuerySet)
    team_qs.order_by.return_value.values.return_value = [
        {"dbid": 10, "name": "Nursing"},
    ]
    mock_team_cls.objects.all.return_value = team_qs

    view = _helper_instance()
    result = view.get_assignees()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assignees = data["assignees"]
    assert len(assignees) == 3
    assert assignees[0] == {"type": "staff", "id": 1, "label": "Jane Doe"}
    assert assignees[1] == {"type": "staff", "id": 2, "label": "John Smith"}
    assert assignees[2] == {"type": "team", "id": 10, "label": "Nursing"}


@patch("hyperscribe.scribe.api.session_view.Team")
@patch("hyperscribe.scribe.api.session_view.Staff")
def test_get_assignees_empty(mock_staff_cls: MagicMock, mock_team_cls: MagicMock) -> None:
    staff_qs = MagicMock(spec=QuerySet)
    staff_qs.order_by.return_value = MagicMock(spec=QuerySet)
    staff_qs.order_by.return_value.values.return_value = []
    mock_staff_cls.objects.filter.return_value = staff_qs

    team_qs = MagicMock(spec=QuerySet)
    team_qs.order_by.return_value = MagicMock(spec=QuerySet)
    team_qs.order_by.return_value.values.return_value = []
    mock_team_cls.objects.all.return_value = team_qs

    view = _helper_instance()
    result = view.get_assignees()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["assignees"] == []


# --- /ordering-providers ---


@patch("hyperscribe.scribe.api.session_view.Staff")
def test_get_ordering_providers_returns_all_results(mock_staff_cls: MagicMock) -> None:
    """Regression: the endpoint must return every eligible provider, not a fixed slice.

    Previously the response was capped at the alphabetically-first 50 providers,
    which silently dropped real prescribers (e.g. anyone with a last name past
    "Cu...") on customers with larger staff rosters.
    """
    staff_objects = [SimpleNamespace(id=f"key-{i}", credentialed_name=f"Provider {i:03d} MD") for i in range(75)]
    ordered_qs = MagicMock(spec=QuerySet)
    ordered_qs.__iter__.return_value = iter(staff_objects)
    distinct_qs = MagicMock(spec=QuerySet)
    distinct_qs.order_by.return_value = ordered_qs
    initial_qs = MagicMock(spec=QuerySet)
    initial_qs.distinct.return_value = distinct_qs
    mock_staff_cls.objects.filter.return_value = initial_qs

    view = _helper_instance()
    result = view.get_ordering_providers()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    providers = data["providers"]
    assert len(providers) == 75
    assert providers[0] == {"id": "key-0", "label": "Provider 000 MD"}
    assert providers[-1] == {"id": "key-74", "label": "Provider 074 MD"}


@patch("hyperscribe.scribe.api.session_view.Staff")
def test_get_ordering_providers_with_search_query(mock_staff_cls: MagicMock) -> None:
    staff_objects = [SimpleNamespace(id="key-001", credentialed_name="Provider 001 MD")]
    filtered_qs = MagicMock(spec=QuerySet)
    filtered_qs.__iter__.return_value = iter(staff_objects)
    ordered_qs = MagicMock(spec=QuerySet)
    ordered_qs.filter.return_value = filtered_qs
    distinct_qs = MagicMock(spec=QuerySet)
    distinct_qs.order_by.return_value = ordered_qs
    initial_qs = MagicMock(spec=QuerySet)
    initial_qs.distinct.return_value = distinct_qs
    mock_staff_cls.objects.filter.return_value = initial_qs

    view = _helper_instance()
    view.request.query_params = {"query": "Provider"}
    result = view.get_ordering_providers()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["providers"] == [{"id": "key-001", "label": "Provider 001 MD"}]
    # The endpoint should have applied the search filter on top of the ordered queryset.
    assert ordered_qs.filter.called


# --- /recommend-commands ---


@patch("hyperscribe.scribe.contacts.resolve_zip_codes", return_value=[])
@patch("hyperscribe.scribe.api.session_view.recommend_commands")
def test_recommend_commands_success(mock_recommend: MagicMock, _mock_zip: MagicMock) -> None:
    mock_recommend.return_value = [
        CommandProposal(
            command_type="medication_statement",
            display="Lisinopril 10mg",
            data={"medication_text": "Lisinopril 10mg", "fdb_code": None, "sig": "Take daily"},
            section_key="_recommended",
        ),
        CommandProposal(
            command_type="allergy",
            display="Penicillin",
            data={
                "allergy_text": "Penicillin",
                "concept_id": 100,
                "concept_id_type": 1,
                "reaction": "rash",
                "severity": "moderate",
            },
            section_key="_recommended",
        ),
    ]

    view = _helper_instance()
    view.secrets["AnthropicAPIKey"] = "test-key"
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note": {
                    "title": "Note",
                    "sections": [
                        {"key": "current_medications", "title": "Current Medications", "text": "Lisinopril 10mg daily"},
                        {"key": "allergies", "title": "Allergies", "text": "Penicillin (rash)"},
                    ],
                },
            }
        )
    )
    result = view.post_recommend_commands()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert len(data["commands"]) == 2
    assert data["commands"][0]["command_type"] == "medication_statement"
    assert data["commands"][0]["section_key"] == "_recommended"
    assert data["commands"][1]["command_type"] == "allergy"
    mock_recommend.assert_called_once()


def test_recommend_commands_missing_api_key() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note": {"title": "Note", "sections": []}}))
    result = view.post_recommend_commands()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    data = json.loads(result[0].content)
    assert "AnthropicAPIKey" in data["error"]


def test_recommend_commands_invalid_json() -> None:
    view = _helper_instance()
    view.secrets["AnthropicAPIKey"] = "test-key"
    view.request = SimpleNamespace(body="not-json")
    result = view.post_recommend_commands()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.contacts.resolve_zip_codes", return_value=[])
@patch("hyperscribe.scribe.api.session_view.recommend_commands")
def test_recommend_commands_backend_error(mock_recommend: MagicMock, _mock_zip: MagicMock) -> None:
    mock_recommend.side_effect = Exception("LLM failure")

    view = _helper_instance()
    view.secrets["AnthropicAPIKey"] = "test-key"
    view.request = SimpleNamespace(body=json.dumps({"note": {"title": "Note", "sections": []}}))
    result = view.post_recommend_commands()

    assert result[0].status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    data = json.loads(result[0].content)
    assert "failed" in data["error"].lower()


@patch("hyperscribe.scribe.contacts.resolve_zip_codes", return_value=[])
@patch("hyperscribe.scribe.api.session_view.annotate_duplicates")
@patch("hyperscribe.scribe.api.session_view.recommend_commands")
def test_recommend_commands_with_note_uuid_triggers_annotation(
    mock_recommend: MagicMock,
    mock_annotate: MagicMock,
    _mock_zip: MagicMock,
) -> None:
    mock_recommend.return_value = [
        CommandProposal(
            command_type="medication_statement",
            display="Lisinopril 10mg",
            data={"medication_text": "Lisinopril 10mg"},
            section_key="_recommended",
        ),
    ]

    view = _helper_instance()
    view.secrets["AnthropicAPIKey"] = "test-key"
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note": {"title": "Note", "sections": []},
                "note_uuid": "note-uuid-456",
            }
        )
    )
    view.post_recommend_commands()
    mock_annotate.assert_called_once()
    assert mock_annotate.call_args.args[1] == "note-uuid-456"


@patch("hyperscribe.scribe.contacts.resolve_zip_codes", return_value=[])
@patch("hyperscribe.scribe.api.session_view.annotate_duplicates")
@patch("hyperscribe.scribe.api.session_view.recommend_commands")
def test_recommend_commands_without_note_uuid_calls_annotate_with_empty(
    mock_recommend: MagicMock,
    mock_annotate: MagicMock,
    _mock_zip: MagicMock,
) -> None:
    mock_recommend.return_value = []

    view = _helper_instance()
    view.secrets["AnthropicAPIKey"] = "test-key"
    view.request = SimpleNamespace(body=json.dumps({"note": {"title": "Note", "sections": []}}))
    view.post_recommend_commands()
    mock_annotate.assert_called_once()
    assert mock_annotate.call_args.args[1] == ""


# --- /summary-progress ---


@patch("hyperscribe.scribe.api.session_view.get_cache")
def test_get_summary_progress_found(mock_get_cache: MagicMock) -> None:
    cache = _mock_cache()
    mock_get_cache.return_value = cache
    cache._store[f"{_PROGRESS_CACHE_KEY_PREFIX}42"] = json.dumps(
        {"step": 2, "total": 5, "label": "Extracting commands"}
    )

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "42"})
    result = view.get_summary_progress()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["step"] == 2
    assert data["total"] == 5
    assert data["label"] == "Extracting commands"


@patch("hyperscribe.scribe.api.session_view.get_cache")
def test_get_summary_progress_not_found(mock_get_cache: MagicMock) -> None:
    mock_get_cache.return_value = _mock_cache()

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "999"})
    result = view.get_summary_progress()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["step"] == -1


# --- /generate-summary ---


@patch("hyperscribe.scribe.contacts.resolve_zip_codes", return_value=[])
@patch("hyperscribe.scribe.api.session_view.annotate_duplicates")
@patch("hyperscribe.scribe.api.session_view.suggest_diagnoses")
@patch("hyperscribe.scribe.api.session_view.recommend_commands")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.Note")
@patch("hyperscribe.scribe.api.session_view.get_cache")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_summary_success(
    get_backend: MagicMock,
    mock_get_cache: MagicMock,
    mock_note: MagicMock,
    mock_transcript: MagicMock,
    mock_summary: MagicMock,
    mock_recommend: MagicMock,
    mock_suggest: MagicMock,
    _mock_annotate: MagicMock,
    _mock_zip: MagicMock,
) -> None:
    cache = _mock_cache()
    mock_get_cache.return_value = cache
    mock_note.objects.values_list.return_value.get.return_value = 55
    # Seed finalized transcript.
    mock_transcript.objects.filter.return_value.values.return_value.first.return_value = {
        "items": [{"text": "I have a headache", "speaker": "patient", "start_offset_ms": 0, "end_offset_ms": 2000}],
        "finalized": True,
    }

    mock_backend = MagicMock()
    mock_backend.generate_note.return_value = ClinicalNote(
        title="SOAP Note",
        sections=[
            NoteSection(key="chief_complaint", title="CC", text="Headache."),
            NoteSection(
                key="assessment_and_plan",
                title="A&P",
                text="Migraine\n- Start sumatriptan",
            ),
        ],
    )
    mock_backend.generate_normalized_data.return_value = NormalizedData(
        conditions=[
            Condition(
                display="Migraine",
                clinical_status="active",
                coding=[CodingEntry(system="ICD-10", code="G43", display="Migraine")],
            )
        ],
        observations=[],
    )
    mock_backend._last_raw_note_response = None
    get_backend.return_value = mock_backend
    mock_recommend.return_value = [
        CommandProposal(
            command_type="medication_statement",
            display="Sumatriptan",
            data={"medication_text": "Sumatriptan"},
            section_key="_recommended",
        ),
    ]
    mock_suggest.return_value = {}

    view = _helper_instance()
    view.secrets["AnthropicAPIKey"] = "test-key"
    view.request = SimpleNamespace(body=json.dumps({"note_id": "55", "note_uuid": "55"}))
    result = view.post_generate_summary()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["note"]["title"] == "SOAP Note"
    assert len(data["commands"]) >= 1
    # Plan should have been split into diagnose commands.
    diagnose_cmds = [c for c in data["commands"] if c["command_type"] == "diagnose"]
    assert len(diagnose_cmds) == 1
    assert diagnose_cmds[0]["data"]["icd10_code"] == "G43"
    assert len(data["recommendations"]) == 1
    assert data["recommendations"][0]["command_type"] == "medication_statement"
    # Summary should be saved to database.
    mock_summary.objects.update_or_create.assert_called_once()


@patch("hyperscribe.scribe.contacts.resolve_zip_codes", return_value=[])
@patch("hyperscribe.scribe.api.session_view.annotate_duplicates")
@patch("hyperscribe.scribe.api.session_view.suggest_diagnoses")
@patch("hyperscribe.scribe.api.session_view.recommend_commands")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.Note")
@patch("hyperscribe.scribe.api.session_view.get_cache")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_summary_preserves_mode_and_template(
    get_backend: MagicMock,
    mock_get_cache: MagicMock,
    mock_note: MagicMock,
    mock_transcript: MagicMock,
    mock_summary: MagicMock,
    mock_recommend: MagicMock,
    mock_suggest: MagicMock,
    _mock_annotate: MagicMock,
    _mock_zip: MagicMock,
) -> None:
    """generate-summary must persist mode and selected_template_name so the
    approve button remains visible even if the frontend callback never fires."""
    cache = _mock_cache()
    mock_get_cache.return_value = cache
    mock_note.objects.values_list.return_value.get.return_value = 55
    mock_transcript.objects.filter.return_value.values.return_value.first.return_value = {
        "items": [{"text": "I have a headache", "speaker": "patient", "start_offset_ms": 0, "end_offset_ms": 2000}],
        "finalized": True,
    }

    mock_backend = MagicMock()
    mock_backend.generate_note.return_value = ClinicalNote(
        title="SOAP Note",
        sections=[NoteSection(key="chief_complaint", title="CC", text="Headache.")],
    )
    mock_backend.generate_normalized_data.return_value = NormalizedData(conditions=[], observations=[])
    mock_backend._last_raw_note_response = None
    get_backend.return_value = mock_backend
    mock_recommend.return_value = []
    mock_suggest.return_value = {}

    view = _helper_instance()
    view.secrets["AnthropicAPIKey"] = "test-key"
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note_id": "55",
                "note_uuid": "55",
                "mode": "ai",
                "selected_template_name": "Subsequent Visit",
            }
        )
    )
    result = view.post_generate_summary()

    assert result[0].status_code == HTTPStatus.OK
    # Verify _save_summary was called with mode and selected_template_name.
    save_call = mock_summary.objects.update_or_create.call_args
    defaults = save_call.kwargs.get("defaults") or save_call[1].get("defaults", {})
    assert defaults["mode"] == "ai"
    assert defaults["selected_template_name"] == "Subsequent Visit"


@patch("hyperscribe.scribe.contacts.resolve_zip_codes", return_value=[])
@patch("hyperscribe.scribe.api.session_view.annotate_duplicates")
@patch("hyperscribe.scribe.api.session_view.suggest_diagnoses")
@patch("hyperscribe.scribe.api.session_view.recommend_commands")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.Note")
@patch("hyperscribe.scribe.api.session_view.get_cache")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_summary_preserves_mode_from_db_when_not_in_request(
    get_backend: MagicMock,
    mock_get_cache: MagicMock,
    mock_note: MagicMock,
    mock_transcript: MagicMock,
    mock_summary: MagicMock,
    mock_recommend: MagicMock,
    mock_suggest: MagicMock,
    _mock_annotate: MagicMock,
    _mock_zip: MagicMock,
) -> None:
    """When the frontend doesn't send mode/selected_template_name (which is
    the normal case), generate-summary must NOT put either key into the
    _save_summary payload — _save_summary's `if key in payload` guard then
    leaves the DB column alone, preserving whatever the session already set.
    This is the symmetric counterpart of the GET-path CAS protection: the
    write path must not fabricate values for fields it doesn't own."""
    cache = _mock_cache()
    mock_get_cache.return_value = cache
    mock_note.objects.values_list.return_value.get.return_value = 55
    mock_transcript.objects.filter.return_value.values.return_value.first.return_value = {
        "items": [{"text": "I have a headache", "speaker": "patient", "start_offset_ms": 0, "end_offset_ms": 2000}],
        "finalized": True,
    }
    # Simulate an existing summary with mode and template already set.
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = {
        "note_data": {},
        "commands": [],
        "approved": False,
        "recommendations": [],
        "unmatched_conditions": [],
        "diagnosis_suggestions": {},
        "selected_template_name": "Subsequent Visit",
        "mode": "ai",
    }

    mock_backend = MagicMock()
    mock_backend.generate_note.return_value = ClinicalNote(
        title="SOAP Note",
        sections=[NoteSection(key="chief_complaint", title="CC", text="Headache.")],
    )
    mock_backend.generate_normalized_data.return_value = NormalizedData(conditions=[], observations=[])
    mock_backend._last_raw_note_response = None
    get_backend.return_value = mock_backend
    mock_recommend.return_value = []
    mock_suggest.return_value = {}

    view = _helper_instance()
    view.secrets["AnthropicAPIKey"] = "test-key"
    # Frontend request does NOT include mode or selected_template_name.
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note_id": "55",
                "note_uuid": "55",
            }
        )
    )
    result = view.post_generate_summary()

    assert result[0].status_code == HTTPStatus.OK
    save_call = mock_summary.objects.update_or_create.call_args
    defaults = save_call.kwargs.get("defaults") or save_call[1].get("defaults", {})
    assert "mode" not in defaults, (
        "generate-summary must not write mode when the frontend omits it — "
        "_save_summary's guard preserves the DB column"
    )
    assert "selected_template_name" not in defaults, (
        "generate-summary must not write selected_template_name when the "
        "frontend omits it — _save_summary's guard preserves the DB column"
    )


@patch("hyperscribe.scribe.contacts.resolve_zip_codes", return_value=[])
@patch("hyperscribe.scribe.api.session_view.annotate_duplicates")
@patch("hyperscribe.scribe.api.session_view.suggest_diagnoses")
@patch("hyperscribe.scribe.api.session_view.recommend_commands")
@patch("hyperscribe.scribe.api.session_view.ScribeAuditLog")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.Note")
@patch("hyperscribe.scribe.api.session_view.get_cache")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_summary_does_not_clobber_concurrent_save_on_cas_miss(
    get_backend: MagicMock,
    mock_get_cache: MagicMock,
    mock_note: MagicMock,
    mock_transcript: MagicMock,
    mock_summary: MagicMock,
    mock_audit: MagicMock,
    mock_recommend: MagicMock,
    mock_suggest: MagicMock,
    _mock_annotate: MagicMock,
    _mock_zip: MagicMock,
) -> None:
    """If a concurrent /save-summary commits a real mode during the heal's
    inference window inside post_generate_summary's _load_summary call,
    _load_summary returns mode=None on CAS miss. generate-summary must not
    forward that None into _save_summary's payload (the prior `str(... or '')`
    pre-load fallback would have laundered it to '', wiping the concurrent
    writer's mode back to '')."""
    cache = _mock_cache()
    mock_get_cache.return_value = cache
    mock_note.objects.values_list.return_value.get.return_value = 55
    mock_transcript.objects.filter.return_value.values.return_value.first.return_value = {
        "items": [{"text": "I have a headache", "speaker": "patient", "start_offset_ms": 0, "end_offset_ms": 2000}],
        "finalized": True,
    }
    # Legacy wiped row: mode='' triggers heal in _load_summary.
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = {
        "note_data": {"sections": [{"key": "hpi", "text": "Pain"}]},
        "commands": [],
        "approved": False,
        "recommendations": [],
        "unmatched_conditions": [],
        "diagnosis_suggestions": {},
        "selected_template_name": "",
        "mode": "",
    }
    # Audit log has START_AI → heal would set mode='ai', but the CAS misses.
    mock_audit.objects.filter.return_value.values_list.return_value.first.return_value = [
        {"type": "START_AI"},
    ]
    # Simulate concurrent /save-summary committing a real mode during the heal:
    # the CAS update matches 0 rows.
    mock_summary.objects.filter.return_value.update.return_value = 0

    mock_backend = MagicMock()
    mock_backend.generate_note.return_value = ClinicalNote(
        title="SOAP Note",
        sections=[NoteSection(key="chief_complaint", title="CC", text="Headache.")],
    )
    mock_backend.generate_normalized_data.return_value = NormalizedData(conditions=[], observations=[])
    mock_backend._last_raw_note_response = None
    get_backend.return_value = mock_backend
    mock_recommend.return_value = []
    mock_suggest.return_value = {}

    view = _helper_instance()
    view.secrets["AnthropicAPIKey"] = "test-key"
    # Frontend doesn't include mode in the generate-summary request body.
    view.request = SimpleNamespace(body=json.dumps({"note_id": "55", "note_uuid": "55"}))
    result = view.post_generate_summary()

    assert result[0].status_code == HTTPStatus.OK
    defaults = mock_summary.objects.update_or_create.call_args.kwargs["defaults"]
    assert "mode" not in defaults, (
        "On CAS miss, generate-summary must leave the mode column alone — "
        "the concurrent writer's value is now authoritative"
    )


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_summary_missing_note_id(get_backend: MagicMock) -> None:
    get_backend.return_value = MagicMock()

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({}))
    result = view.post_generate_summary()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "note_id" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.Note")
@patch("hyperscribe.scribe.api.session_view.get_cache")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_summary_no_transcript(
    get_backend: MagicMock, mock_get_cache: MagicMock, mock_note: MagicMock, mock_transcript: MagicMock
) -> None:
    mock_get_cache.return_value = _mock_cache()
    mock_note.objects.values_list.return_value.get.return_value = 99
    mock_transcript.objects.filter.return_value.values.return_value.first.return_value = None
    get_backend.return_value = MagicMock()

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note_id": "99"}))
    result = view.post_generate_summary()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "No transcript" in json.loads(result[0].content)["error"]


def test_generate_summary_invalid_json() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body="not-json")
    result = view.post_generate_summary()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.Note")
@patch("hyperscribe.scribe.api.session_view.get_cache")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_summary_backend_error(
    get_backend: MagicMock, mock_get_cache: MagicMock, mock_note: MagicMock, mock_transcript: MagicMock
) -> None:
    cache = _mock_cache()
    mock_get_cache.return_value = cache
    mock_note.objects.values_list.return_value.get.return_value = 42
    mock_transcript.objects.filter.return_value.values.return_value.first.return_value = {
        "items": [{"text": "hi", "speaker": "patient"}],
        "finalized": True,
    }

    mock_backend = MagicMock()
    mock_backend.generate_note.side_effect = ScribeError("Note generation failed")
    get_backend.return_value = mock_backend

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note_id": "42"}))
    result = view.post_generate_summary()

    assert result[0].status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "Note generation failed" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.contacts.resolve_zip_codes", return_value=[])
@patch("hyperscribe.scribe.api.session_view.annotate_duplicates")
@patch("hyperscribe.scribe.api.session_view.recommend_commands")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.Note")
@patch("hyperscribe.scribe.api.session_view.get_cache")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_summary_non_critical_failures(
    get_backend: MagicMock,
    mock_get_cache: MagicMock,
    mock_note: MagicMock,
    mock_transcript: MagicMock,
    _mock_summary: MagicMock,
    mock_recommend: MagicMock,
    _mock_annotate: MagicMock,
    _mock_zip: MagicMock,
) -> None:
    """When non-critical steps fail, the response still includes what succeeded."""
    cache = _mock_cache()
    mock_get_cache.return_value = cache
    mock_note.objects.values_list.return_value.get.return_value = 77
    mock_transcript.objects.filter.return_value.values.return_value.first.return_value = {
        "items": [{"text": "hi", "speaker": "patient"}],
        "finalized": True,
    }

    mock_backend = MagicMock()
    mock_backend.generate_note.return_value = ClinicalNote(
        title="Note", sections=[NoteSection(key="chief_complaint", title="CC", text="Pain.")]
    )
    mock_backend.generate_normalized_data.side_effect = Exception("Normalized data failed")
    get_backend.return_value = mock_backend
    mock_recommend.side_effect = Exception("Recommend failed")

    view = _helper_instance()
    view.secrets["AnthropicAPIKey"] = "test-key"
    view.request = SimpleNamespace(body=json.dumps({"note_id": "77", "note_uuid": "77"}))
    result = view.post_generate_summary()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["note"]["title"] == "Note"
    assert len(data["commands"]) >= 1
    assert data["recommendations"] == []
    assert data["diagnosis_suggestions"] == {}


@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.Note")
@patch("hyperscribe.scribe.api.session_view.get_cache")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_summary_writes_progress(
    get_backend: MagicMock,
    mock_get_cache: MagicMock,
    mock_note: MagicMock,
    mock_transcript: MagicMock,
    _mock_summary: MagicMock,
) -> None:
    """Progress cache is updated during the pipeline."""
    cache = _mock_cache()
    mock_get_cache.return_value = cache
    mock_note.objects.values_list.return_value.get.return_value = 88
    mock_transcript.objects.filter.return_value.values.return_value.first.return_value = {
        "items": [{"text": "test", "speaker": "patient"}],
        "finalized": True,
    }

    mock_backend = MagicMock()
    mock_backend.generate_note.return_value = ClinicalNote(title="Note", sections=[])
    mock_backend.generate_normalized_data.return_value = NormalizedData(conditions=[], observations=[])
    get_backend.return_value = mock_backend

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note_id": "88"}))
    view.post_generate_summary()

    # After completion, progress cache should have the last step written.
    progress_key = f"{_PROGRESS_CACHE_KEY_PREFIX}88"
    assert progress_key in cache._store
    progress = json.loads(cache._store[progress_key])
    assert progress["step"] == len(SUMMARY_STEPS) - 1
    assert progress["total"] == len(SUMMARY_STEPS)


# --- /carry-forward-background ---
#
# Focused read endpoint the frontend hits when a new ``assess`` command is
# created client-side (handleAddCondition: manual "+ Add Condition"). The
# already-existing /insert-commands belt covers the convert-at-approve path,
# but the user needs to SEE the carry-forward in the edit drawer BEFORE
# approving, so this endpoint exists to populate the background text in the UI.


@patch("hyperscribe.scribe.api.session_view.carry_forward_assess_background")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_carry_forward_background_success(mock_note: MagicMock, mock_helper: MagicMock) -> None:
    """Happy path: a prior signed assessment exists for the (patient, condition).

    The endpoint reuses ``carry_forward_assess_background`` (the same helper
    /insert-commands runs server-side), so we mock the helper and assert the
    endpoint propagates the mutation it makes to the throwaway dict.
    """
    mock_note.objects.select_related.return_value.get.return_value = MagicMock()

    # Snapshot the dict at call time — ``mock.call_args`` holds a reference, so
    # by the time we inspect it the side_effect's mutation would have already
    # landed. Capture the pre-mutation state inside the side_effect itself.
    captured_initial_state: dict[str, Any] = {}

    def _set_background(data: dict[str, Any], _note: Any) -> None:
        captured_initial_state.update(data)
        data["background"] = "This is zee background"

    mock_helper.side_effect = _set_background

    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps({"note_uuid": "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0", "condition_id": "cond-1"})
    )
    result = view.post_carry_forward_background()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content) == {"background": "This is zee background"}

    # The throwaway dict the endpoint passes to the helper must carry the
    # condition_id (the helper short-circuits on missing condition_id), and
    # must NOT pre-set ``background`` (the helper short-circuits on a
    # populated background — that would defeat the lookup).
    assert captured_initial_state["condition_id"] == "cond-1"
    assert "background" not in captured_initial_state or not captured_initial_state.get("background")


@patch("hyperscribe.scribe.api.session_view.carry_forward_assess_background")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_carry_forward_background_no_prior(mock_note: MagicMock, mock_helper: MagicMock) -> None:
    """No prior signed assessment: helper leaves the throwaway dict untouched.

    The endpoint returns 200 with ``{"background": null}`` so the frontend can
    distinguish "no carry-forward to apply" from a network/server error.
    """
    mock_note.objects.select_related.return_value.get.return_value = MagicMock()
    # Helper short-circuits and does not set ``background`` — simulate by no-op.
    mock_helper.side_effect = lambda _data, _note: None

    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps({"note_uuid": "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0", "condition_id": "cond-1"})
    )
    result = view.post_carry_forward_background()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content) == {"background": None}


def test_carry_forward_background_missing_note_uuid() -> None:
    """Missing or empty note_uuid in the body returns 400. The auth helper
    enforces the same check — but we surface the error before auth too, so a
    malformed payload doesn't hit the DB."""
    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"condition_id": "cond-1"}))
    result = view.post_carry_forward_background()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "note_uuid" in json.loads(result[0].content)["error"]


def test_carry_forward_background_missing_condition_id() -> None:
    """Missing or empty condition_id returns 400. Without a condition_id the
    helper has nothing to scope by; surface the error explicitly rather than
    silently returning null (which would mask a frontend bug)."""
    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0"}))
    result = view.post_carry_forward_background()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "condition_id" in json.loads(result[0].content)["error"]


def test_carry_forward_background_invalid_json() -> None:
    """Non-JSON body returns 400 — same shape as every other POST endpoint."""
    view = _helper_instance()
    view.request = SimpleNamespace(body="not-json")
    result = view.post_carry_forward_background()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.api.session_view.Note")
def test_carry_forward_background_note_not_found(mock_note: MagicMock) -> None:
    """If the auth helper passes but the select_related lookup raises (e.g.
    malformed UUID that reached the SQL layer, or a race where the note was
    deleted between auth and lookup), return 404 rather than 500.

    Note: in normal flow, ``_authorize_edit`` short-circuits with 404 first.
    This test specifically pins the defensive try/except inside the endpoint.
    """
    from canvas_sdk.v1.data.note import Note as RealNote

    mock_note.objects.select_related.return_value.get.side_effect = RealNote.DoesNotExist
    mock_note.DoesNotExist = RealNote.DoesNotExist

    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps({"note_uuid": "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0", "condition_id": "cond-1"})
    )
    result = view.post_carry_forward_background()

    assert result[0].status_code == HTTPStatus.NOT_FOUND


@pytest.mark.no_authorize_bypass
@patch("hyperscribe.scribe.api.session_view.Helper.editable_note", return_value=True)
@patch("hyperscribe.scribe.api.session_view.Note")
def test_carry_forward_background_unauthorized(mock_note: MagicMock, _editable: MagicMock) -> None:
    """The real auth helper (no bypass): a request from a staff who is NOT the
    note's provider returns 403. Pins that the new endpoint is gated identically
    to every other mutating endpoint (defense in depth — the endpoint is
    technically read-only, but it leaks ``has a prior assessment``-shaped
    metadata about another provider's patient if left open)."""
    mock_note.objects.values.return_value.get.return_value = {"dbid": 42, "provider__id": "other-staff"}

    view = _helper_instance(staff_id="staff-key-abc")
    view.request = SimpleNamespace(
        headers={"canvas-logged-in-user-id": "staff-key-abc"},
        body=json.dumps({"note_uuid": "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0", "condition_id": "cond-1"}),
    )
    result = view.post_carry_forward_background()

    assert result[0].status_code == HTTPStatus.FORBIDDEN
