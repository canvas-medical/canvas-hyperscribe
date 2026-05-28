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
        "was_finalized": False,
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
    assert json.loads(result[0].content) == {"note": None, "commands": [], "approved": False, "was_finalized": False}


def test_get_summary_missing_note_id() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={})
    result = view.get_summary()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST


# --- _load_summary mode self-heal ---


def _heal_summary_row(note_data: Any = None, commands: Any = None, mode: str | None = None) -> dict[str, Any]:
    return {
        "note_data": note_data or {},
        "commands": commands or [],
        "approved": False,
        "was_finalized": False,
        "recommendations": [],
        "unmatched_conditions": [],
        "diagnosis_suggestions": {},
        "selected_template_name": "",
        "mode": mode if mode is not None else "",
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


@patch("hyperscribe.scribe.api.session_view.ScribeTranscript")
@patch("hyperscribe.scribe.api.session_view.ScribeAuditLog")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_get_summary_surfaces_was_finalized(
    mock_note: MagicMock, mock_summary: MagicMock, mock_audit: MagicMock, mock_transcript: MagicMock
) -> None:
    """/summary GET response includes the was_finalized latch so the
    frontend can render the amendment pill on reload."""
    mock_note.objects.values_list.return_value.get.return_value = 42
    summary_row = _heal_summary_row(note_data={"sections": []}, mode="ai")
    summary_row["was_finalized"] = True
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = summary_row
    mock_audit.objects.filter.return_value.values_list.return_value.first.return_value = []

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "42"})
    result = view.get_summary()

    assert result[0].status_code == HTTPStatus.OK
    body = json.loads(result[0].content)
    assert body["was_finalized"] is True


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


@patch("hyperscribe.scribe.api.session_view.Note")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
def test_save_summary_latches_was_finalized_on_approve(mock_summary: MagicMock, mock_note: MagicMock) -> None:
    """First save with approved=True sets was_finalized=True via the defaults
    passed to update_or_create. Subsequent saves with approved=False keep
    was_finalized=True implicitly because the field is omitted from defaults."""
    mock_note.objects.values_list.return_value.get.return_value = 42

    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note_id": "42",
                "note": {},
                "commands": [],
                "approved": True,
            }
        )
    )
    view.post_save_summary()

    mock_summary.objects.update_or_create.assert_called_once()
    _, kwargs = mock_summary.objects.update_or_create.call_args
    assert kwargs["note_id"] == 42
    assert kwargs["defaults"]["approved"] is True
    assert kwargs["defaults"]["was_finalized"] is True


@patch("hyperscribe.scribe.api.session_view.Note")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
def test_save_summary_does_not_set_was_finalized_when_unapproved(mock_summary: MagicMock, mock_note: MagicMock) -> None:
    """Save with approved=False must NOT include was_finalized in defaults,
    so the existing column value (potentially True from a prior approval)
    is preserved by update_or_create."""
    mock_note.objects.values_list.return_value.get.return_value = 42

    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note_id": "42",
                "note": {},
                "commands": [],
                "approved": False,
            }
        )
    )
    view.post_save_summary()

    mock_summary.objects.update_or_create.assert_called_once()
    _, kwargs = mock_summary.objects.update_or_create.call_args
    assert "was_finalized" not in kwargs["defaults"]


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


def test_summary_js_cache_flip_to_approved_true_is_unconditional_on_success() -> None:
    """KOALA-5485 cache-flip regression: in ``handleInsert``'s
    ``/insert-commands`` success branch, the ``saveSummaryToCache(...true...)``
    call must fire UNCONDITIONALLY - NOT gated on ``data.attempted.length > 0``.

    Edge case: in amend-mode where the user saves with zero edits in any
    editable section (or empty-note approval), ``data.attempted`` is empty.
    If the cache write is gated on ``data.attempted.length > 0``,
    ``setApproved(true)`` updates React state in memory but the cache holds
    ``approved=false`` - on page reload the UI reverts to pre-approval.

    Pinning approach (structural-static, since this repo has no JS test
    framework): two assertions, both required:
      1. The marker comment ``CACHE_FLIP_UNCONDITIONAL_ON_APPROVE_SUCCESS`` is
         present (intent / trace marker for future maintainers).
      2. Inside ``handleInsert``'s success branch, a ``saveSummaryToCache(...true...)``
         call appears AFTER the closing brace of the
         ``if (data.attempted && data.attempted.length > 0) {...}`` block - i.e.,
         a sibling, not a child. If the call is moved back inside the gate, this
         assertion fails.

    Behavioral caveat: this is a structural pin, not a runtime behavioral pin.
    It does NOT execute the React code. A regression that deletes the comment
    while keeping the call gets caught by (1); a regression that moves the call
    back inside the gate while keeping the comment gets caught by (2). A
    behavioral pin would require a JS test infra, which is out of scope.
    """
    from pathlib import Path

    summary_js = Path(__file__).resolve().parents[4] / "hyperscribe" / "scribe" / "static" / "summary.js"
    src = summary_js.read_text()

    # (1) Marker comment - intent / trace breadcrumb.
    assert "CACHE_FLIP_UNCONDITIONAL_ON_APPROVE_SUCCESS" in src, (
        "summary.js handleInsert success branch is missing the "
        "CACHE_FLIP_UNCONDITIONAL_ON_APPROVE_SUCCESS marker. Without the "
        "unconditional write, amend-mode Save with zero edits leaves the cache "
        "at approved=false, so a page reload reverts the UI. Add a "
        "saveSummaryToCache(..., true, ...) on the success branch, OUTSIDE the "
        "`if (data.attempted && data.attempted.length > 0)` gate. Mark it with "
        "the CACHE_FLIP_UNCONDITIONAL_ON_APPROVE_SUCCESS comment."
    )

    # (2) Structural: the `if (data.attempted && data.attempted.length > 0) {...}`
    # block must be CLOSED before an unconditional saveSummaryToCache(..., true, ...)
    # call. If the call moves back inside the gate, the close brace of the gate
    # comes AFTER the call.
    gate_marker = "if (data.attempted && data.attempted.length > 0) {"
    gate_idx = src.find(gate_marker)
    assert gate_idx != -1, (
        "Expected to find the `if (data.attempted && data.attempted.length > 0) {` "
        "guard inside handleInsert. If this gate has been removed entirely, "
        "that's also a valid fix - update the test."
    )

    # Walk forward from after the gate's opening brace, counting braces, to find
    # its matching close.
    open_brace_pos = gate_idx + len(gate_marker) - 1  # position of the `{`
    depth = 0
    close_pos = -1
    for i in range(open_brace_pos, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                close_pos = i
                break
    assert close_pos != -1, "Could not find matching close brace for the data.attempted gate"

    # Match `saveSummaryToCache(noteData, <any>, true,` with `true` as the third arg.
    # This is the post-insert success cache flip. The amend-branch cache write is
    # earlier in the file (before the gate), so it doesn't show up in `after_gate`.
    after_gate = src[close_pos + 1 :]
    unconditional_pattern = re.compile(r"saveSummaryToCache\s*\(\s*noteData\s*,[^,]+,\s*true\s*,")
    assert unconditional_pattern.search(after_gate), (
        "The unconditional `saveSummaryToCache(noteData, ..., true, ...)` call "
        "must appear OUTSIDE (after the closing brace of) the "
        "`if (data.attempted && data.attempted.length > 0) {...}` block in "
        "handleInsert's success branch. Currently it appears to be missing or "
        "still nested inside the gate - which leaves amend-mode-zero-edits at "
        "cache.approved=false."
    )


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_effects")
def test_insert_commands_audit_payload_excludes_display_phi(mock_build: MagicMock, mock_audit: MagicMock) -> None:
    """HIPAA regression: the INSERT_COMMANDS audit payload must NOT carry the
    ``display`` field. ``display`` is free-text clinical narrative for HPI / ROS /
    PE / lab_results / current_medications; persisting it into
    ``ScribeAuditLog.events`` is PHI in a log, even with 80-char truncation.
    The audit retains structural identifiers (type, section_key) and aggregate
    counts - enough signal for incident triage without leaking content. Mirrors
    the AMEND_EXISTING_COMMANDS PHI hardening (KOALA-5485).
    """
    mock_effect = MagicMock()
    attempted = [
        {"command_uuid": "u1", "command_type": "hpi", "display": "Back pain"},
    ]
    mock_build.return_value = ([mock_effect], [], attempted, [])

    view = _helper_instance()
    commands = [
        {
            "command_type": "hpi",
            "section_key": "history_of_present_illness",
            "data": {"narrative": "Patient reports severe headache for 3 days, PHI here"},
            "display": "Patient reports severe headache for 3 days (clinical narrative)",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    view.post_insert_commands()

    audit_calls = [c for c in mock_audit.call_args_list if c.args[1] == "INSERT_COMMANDS"]
    assert len(audit_calls) == 1
    payload = audit_calls[0].args[2]
    assert payload["commands"], "expected at least one command entry to assert against"
    for entry in payload["commands"]:
        assert "display" not in entry, (
            f"INSERT_COMMANDS audit payload must not carry 'display' (PHI risk); got: {sorted(entry.keys())}"
        )


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.Command")
def test_verify_commands_audit_payload_excludes_display_phi(mock_command: MagicMock, mock_audit: MagicMock) -> None:
    """HIPAA regression: the COMMANDS_VERIFIED audit payload must NOT carry the
    ``display`` field in either the ``verified`` or ``failed`` lists. Same
    rationale as INSERT_COMMANDS / AMEND_EXISTING_COMMANDS: ``display`` is
    free-text clinical narrative for many command types; persisting it (even
    truncated) is PHI in a log. The audit retains structural identifiers
    (type, command_uuid) and aggregate totals.
    """
    # Simulate: 1 verified (anchor present), 1 failed (no anchor).
    mock_command.objects.filter.return_value.values.return_value = [
        {"id": "uuid-verified", "anchor_object_type": "X", "anchor_object_dbid": 42},
        {"id": "uuid-failed", "anchor_object_type": "X", "anchor_object_dbid": None},
    ]

    view = _helper_instance()
    attempted = [
        {
            "command_uuid": "uuid-verified",
            "command_type": "hpi",
            "display": "Patient reports severe headache with photophobia (PHI)",
        },
        {
            "command_uuid": "uuid-failed",
            "command_type": "ros",
            "display": "Denies fever, chills; positive cough and shortness of breath (PHI)",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "attempted": attempted}))
    view.post_verify_commands()

    audit_calls = [c for c in mock_audit.call_args_list if c.args[1] == "COMMANDS_VERIFIED"]
    assert len(audit_calls) == 1
    payload = audit_calls[0].args[2]
    for entry in payload.get("verified", []):
        assert "display" not in entry, (
            f"COMMANDS_VERIFIED 'verified' entries must not carry 'display' (PHI risk); got: {sorted(entry.keys())}"
        )
    for entry in payload.get("failed", []):
        assert "display" not in entry, (
            f"COMMANDS_VERIFIED 'failed' entries must not carry 'display' (PHI risk); got: {sorted(entry.keys())}"
        )


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


# --- /edit-existing-commands (KOALA-5485) ---


class _StubUUID:
    """Stand-in for the ``uuid.UUID`` objects returned by
    ``Command.objects.values_list("id", ...)`` against Postgres.

    The Postgres backend yields ``uuid.UUID`` instances for ``UUIDField``
    columns, NOT strings. ``hash(UUID(s)) != hash(s)``, so a dict keyed by
    the raw return values misses every string-keyed lookup - that's the
    bug that turned every legitimate amendment into a ``command_not_found``
    409 in UAT (KOALA-5485 iter-4 fix).

    This stub mirrors the salient behavior of ``uuid.UUID`` for the test:
    string-ish but with a non-string hash, so a faulty implementation that
    forgets to coerce will fail loudly. We can't use ``uuid.UUID`` directly
    here because the test fixtures use human-readable identifiers like
    ``"old-hpi-uuid"`` that aren't valid UUIDs - swapping every fixture to
    a real UUID would balloon the diff without improving the regression
    signal this stub already gives.
    """

    __slots__ = ("_s",)

    def __init__(self, s: str) -> None:
        self._s = s

    def __str__(self) -> str:
        return self._s

    def __repr__(self) -> str:
        return f"_StubUUID({self._s!r})"

    def __hash__(self) -> int:
        # Critically, the hash MUST differ from ``hash(self._s)`` - that's the
        # production type-mismatch we're modeling.
        return hash(("uuid", self._s))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _StubUUID):
            return self._s == other._s
        return NotImplemented


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_edit_effects")
@patch("hyperscribe.scribe.api.session_view.Command")
def test_edit_existing_commands_rfv_direct_edit(
    mock_command: MagicMock, mock_build: MagicMock, mock_audit: MagicMock
) -> None:
    """Direct EDIT for chief_complaint surfaces the same uuid for old/new."""
    mock_effect = MagicMock()
    attempted = [
        {
            "section_key": "chief_complaint",
            "command_type": "rfv",
            "old_command_uuid": "rfv-uuid",
            "new_command_uuid": "rfv-uuid",
            "mode": "direct_edit",
            "display": "Headache",
        },
    ]
    mock_build.return_value = ([mock_effect], attempted)
    # State check: the RFV row is currently 'staged' (the only valid state for direct EDIT).
    # ``_StubUUID`` mirrors Postgres' return type for ``UUIDField`` columns:
    # the production query returns ``uuid.UUID`` instances, not strings, and the
    # session view must coerce them to ``str`` for the string-keyed lookup.
    mock_command.objects.filter.return_value.values_list.return_value = [
        (_StubUUID("rfv-uuid"), "staged"),
    ]

    view = _helper_instance()
    commands = [
        {
            "command_type": "rfv",
            "command_uuid": "rfv-uuid",
            "section_key": "chief_complaint",
            "data": {"comment": "Headache"},
            "display": "Headache",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    result = view.post_edit_existing_commands()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["attempted"] == attempted
    # KOALA-5485: 'rejected' is no longer surfaced in the response. Silent
    # drops are logged at WARN inside build_amend_edit_effects instead.
    assert "rejected" not in data
    assert len(result) == 2  # JSONResponse + 1 effect
    assert result[1] is mock_effect
    mock_build.assert_called_once_with(commands, "note-uuid-123")
    mock_audit.assert_called_once()
    audit_call = mock_audit.call_args
    assert audit_call.args[0] == "note-uuid-123"
    assert audit_call.args[1] == "AMEND_EXISTING_COMMANDS"
    assert audit_call.args[2]["edit_count"] == 1
    assert audit_call.args[2]["effect_count"] == 1
    assert audit_call.args[2]["entries"][0]["mode"] == "direct_edit"


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_edit_effects")
@patch("hyperscribe.scribe.api.session_view.Command")
def test_edit_existing_commands_hpi_void_recreate(
    mock_command: MagicMock, mock_build: MagicMock, mock_audit: MagicMock
) -> None:
    """Void+recreate for HPI surfaces a different uuid for new vs old."""
    eie_effect = MagicMock()
    originate_effect = MagicMock()
    commit_effect = MagicMock()
    attempted = [
        {
            "section_key": "history_of_present_illness",
            "command_type": "hpi",
            "old_command_uuid": "old-hpi-uuid",
            "new_command_uuid": "new-hpi-uuid",
            "mode": "void_recreate",
            "display": "Two weeks of headaches",
        },
    ]
    mock_build.return_value = ([eie_effect, originate_effect, commit_effect], attempted)
    # State check: HPI row is currently 'committed' - valid for void+recreate.
    # See ``_StubUUID`` docstring: Postgres ``uuid`` columns return ``UUID``
    # objects, not strings.
    mock_command.objects.filter.return_value.values_list.return_value = [
        (_StubUUID("old-hpi-uuid"), "committed"),
    ]

    view = _helper_instance()
    commands = [
        {
            "command_type": "hpi",
            "command_uuid": "old-hpi-uuid",
            "section_key": "history_of_present_illness",
            "data": {"narrative": "Two weeks of headaches"},
            "display": "Two weeks of headaches",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    result = view.post_edit_existing_commands()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["attempted"] == attempted
    assert len(result) == 4  # JSONResponse + 3 effects
    audit_call = mock_audit.call_args
    assert audit_call.args[1] == "AMEND_EXISTING_COMMANDS"
    assert audit_call.args[2]["entries"][0]["mode"] == "void_recreate"
    assert audit_call.args[2]["entries"][0]["old_command_uuid"] == "old-hpi-uuid"
    assert audit_call.args[2]["entries"][0]["new_command_uuid"] == "new-hpi-uuid"


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_edit_effects")
def test_edit_existing_commands_silently_drops_disallowed_section(mock_build: MagicMock, mock_audit: MagicMock) -> None:
    """Sections not in EDITABLE_AMEND_SECTIONS are silently dropped (logged at WARN
    inside build_amend_edit_effects). The response carries only the attempted
    list - no parallel `rejected` field. Rationale: defense-in-depth, not UX -
    the frontend should never send a non-editable section in the first place;
    surfacing them as a structured response field encourages relying on it.
    """
    mock_build.return_value = ([], [])

    view = _helper_instance()
    commands = [
        {
            "command_type": "prescribe",
            "command_uuid": "rx-uuid",
            "section_key": "_recommended",  # not in EDITABLE_AMEND_SECTIONS
            "data": {"sig": "daily"},
            "display": "Lisinopril",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    result = view.post_edit_existing_commands()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["attempted"] == []
    # No `rejected` parallel field anymore.
    assert "rejected" not in data
    # Audit still gets the (empty) entries list under the renamed type.
    audit_call = mock_audit.call_args
    assert audit_call.args[1] == "AMEND_EXISTING_COMMANDS"
    assert audit_call.args[2]["edit_count"] == 0
    assert audit_call.args[2]["entries"] == []


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_edit_effects")
def test_edit_existing_commands_silently_drops_missing_command_uuid(
    mock_build: MagicMock, mock_audit: MagicMock
) -> None:
    """An editable section without a command_uuid is silently dropped, not silently
    turned into a fresh insert. The frontend should never submit this shape; if it
    does, the drop is logged at WARN inside build_amend_edit_effects.
    """
    mock_build.return_value = ([], [])

    view = _helper_instance()
    commands = [
        {
            "command_type": "rfv",
            "section_key": "chief_complaint",
            "data": {"comment": "Headache"},
            "display": "Headache",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    result = view.post_edit_existing_commands()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["attempted"] == []
    assert "rejected" not in data


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_edit_effects")
def test_edit_existing_commands_validation_error(mock_build: MagicMock, mock_audit: MagicMock) -> None:
    """Per-field validation runs against amendment edits too - over-long narratives bounce."""
    view = _helper_instance()
    commands = [
        {
            "command_type": "hpi",
            "command_uuid": "old-hpi-uuid",
            "section_key": "history_of_present_illness",
            "data": {"narrative": "x" * 999999},  # this won't trip current rules but we use a real rule below
        },
        # Use a known rule that DOES trip: prescribe sig over 1000 chars.
        {
            "command_type": "prescribe",
            "command_uuid": "old-rx-uuid",
            "section_key": "chief_complaint",  # ignored when validation fails first
            "data": {"sig": "x" * 1001},
            "display": "Rx",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    result = view.post_edit_existing_commands()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    payload = json.loads(result[0].content)
    assert "validation_errors" in payload
    mock_build.assert_not_called()
    # Validation failure still gets audited.
    audit_event_types = [c.args[1] for c in mock_audit.call_args_list]
    assert "VALIDATION_FAILED" in audit_event_types


def test_edit_existing_commands_missing_note_uuid() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"commands": []}))
    result = view.post_edit_existing_commands()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "note_uuid" in json.loads(result[0].content)["error"]


def test_edit_existing_commands_invalid_json() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body="not-json")
    result = view.post_edit_existing_commands()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.api.session_view.Command")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_edit_effects")
def test_edit_existing_commands_does_not_touch_scribe_summary(
    mock_build: MagicMock,
    mock_audit: MagicMock,
    mock_summary: MagicMock,
    mock_command: MagicMock,
) -> None:
    """KOALA-5485: amendment edits must NOT write to ScribeSummary.

    The ``was_finalized`` latch is set by ``/save-summary`` on first approval
    and is intentionally one-way: any number of amendment edit roundtrips
    must leave it True. Pinning this at the endpoint level keeps a future
    refactor from accidentally introducing a write that clears the latch
    (which would re-show the "Accept and sign" wording and break the
    distinction between fresh approval and amendment).
    """
    mock_effect = MagicMock()
    mock_build.return_value = (
        [mock_effect],
        [
            {
                "section_key": "chief_complaint",
                "command_type": "rfv",
                "old_command_uuid": "rfv-uuid",
                "new_command_uuid": "rfv-uuid",
                "mode": "direct_edit",
                "display": "Headache",
            },
        ],
    )
    mock_command.objects.filter.return_value.values_list.return_value = [
        (_StubUUID("rfv-uuid"), "staged"),
    ]

    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note_uuid": "note-uuid-123",
                "commands": [
                    {
                        "command_type": "rfv",
                        "command_uuid": "rfv-uuid",
                        "section_key": "chief_complaint",
                        "data": {"comment": "Headache"},
                        "display": "Headache",
                    },
                ],
            }
        )
    )
    view.post_edit_existing_commands()

    mock_summary.objects.update_or_create.assert_not_called()
    mock_summary.objects.create.assert_not_called()
    mock_summary.objects.filter.assert_not_called()
    mock_summary.objects.get.assert_not_called()


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_edit_effects")
@patch("hyperscribe.scribe.api.session_view.Command")
def test_edit_existing_commands_rejects_stale_amend_on_already_voided_row(
    mock_command: MagicMock, mock_build: MagicMock, mock_audit: MagicMock
) -> None:
    """Cross-tab concurrency: Tab A amends HPI X -> Y (X is now entered_in_error).
    Tab B (stale, still showing X) submits its own amend against X. The backend
    must reject Tab B's amend with HTTP 409 so the frontend can prompt reload,
    not happily emit EIE(X) on an already-voided row.
    """
    # Tab B's request: amend HPI against uuid X.
    # State in DB: X is now 'entered_in_error' (Tab A already voided it).
    mock_command.objects.filter.return_value.values_list.return_value = [
        (_StubUUID("old-hpi-uuid"), "entered_in_error"),
    ]

    view = _helper_instance()
    commands = [
        {
            "command_type": "hpi",
            "command_uuid": "old-hpi-uuid",
            "section_key": "history_of_present_illness",
            "data": {"narrative": "Tab B's stale edit"},
            "display": "Tab B's stale edit",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    result = view.post_edit_existing_commands()

    assert result[0].status_code == HTTPStatus.CONFLICT
    body = json.loads(result[0].content)
    assert "error" in body
    assert "conflicts" in body
    assert len(body["conflicts"]) == 1
    conflict = body["conflicts"][0]
    assert conflict["command_uuid"] == "old-hpi-uuid"
    assert conflict["current_state"] == "entered_in_error"
    assert conflict["reason"] == "state_mismatch_already_voided"

    # Build must NOT have been called - no effects emitted on conflict.
    mock_build.assert_not_called()
    # Conflict audit fired with the renamed audit type.
    audit_types = [c.args[1] for c in mock_audit.call_args_list]
    assert "AMEND_CONFLICT" in audit_types


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_edit_effects")
@patch("hyperscribe.scribe.api.session_view.Command")
def test_edit_existing_commands_rejects_direct_edit_on_non_staged_rfv(
    mock_command: MagicMock, mock_build: MagicMock, mock_audit: MagicMock
) -> None:
    """RFV (chief_complaint) direct-EDIT requires the row to be 'staged'. If
    a future home-app change starts committing RFV, the direct EDIT would be
    rejected with "Command must be staged in order to be edited." The
    state-check catches this in the plugin first.
    """
    mock_command.objects.filter.return_value.values_list.return_value = [
        (_StubUUID("rfv-uuid"), "committed"),
    ]

    view = _helper_instance()
    commands = [
        {
            "command_type": "rfv",
            "command_uuid": "rfv-uuid",
            "section_key": "chief_complaint",
            "data": {"comment": "Tab B's stale CC edit"},
            "display": "Tab B's stale CC edit",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    result = view.post_edit_existing_commands()

    assert result[0].status_code == HTTPStatus.CONFLICT
    body = json.loads(result[0].content)
    assert body["conflicts"][0]["reason"] == "state_mismatch_expected_staged"
    assert body["conflicts"][0]["current_state"] == "committed"
    mock_build.assert_not_called()


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_edit_effects")
@patch("hyperscribe.scribe.api.session_view.Command")
def test_edit_existing_commands_rejects_when_command_uuid_missing_from_db(
    mock_command: MagicMock, mock_build: MagicMock, mock_audit: MagicMock
) -> None:
    """If a proposal's command_uuid doesn't resolve to any Command row, treat
    it as a conflict (e.g., stale frontend cache, deleted note). Surface it
    rather than silently no-op or emit EIE on a non-existent row.
    """
    # Filter returns nothing for the requested uuid.
    mock_command.objects.filter.return_value.values_list.return_value = []

    view = _helper_instance()
    commands = [
        {
            "command_type": "hpi",
            "command_uuid": "ghost-uuid",
            "section_key": "history_of_present_illness",
            "data": {"narrative": "edit"},
            "display": "edit",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    result = view.post_edit_existing_commands()

    assert result[0].status_code == HTTPStatus.CONFLICT
    body = json.loads(result[0].content)
    assert body["conflicts"][0]["reason"] == "command_not_found"
    assert body["conflicts"][0]["current_state"] == "missing"


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_edit_effects")
@patch("hyperscribe.scribe.api.session_view.Command")
def test_edit_existing_commands_state_lookup_handles_uuid_type_from_postgres(
    mock_command: MagicMock, mock_build: MagicMock, mock_audit: MagicMock
) -> None:
    """KOALA-5485 regression: ``Command.id`` is a UUIDField backed by
    Postgres ``uuid``, so ``.values_list("id", ...)`` yields ``uuid.UUID``
    instances, not strings. ``hash(UUID(s)) != hash(s)``, so a dict keyed
    by the raw return values misses every string-keyed lookup - turning
    every legitimate amendment into a spurious ``command_not_found`` 409.

    This test pins the type-coercion path: the state-lookup dict MUST be
    keyed by ``str``, and the ``cmd_uuid`` (a string from JSON) MUST
    resolve. The other amendment tests use ``_StubUUID`` to enforce this
    invariant on the type-mismatch axis without relying on a real Postgres
    cursor. This test isolates the contract.
    """
    mock_effect = MagicMock()
    attempted = [
        {
            "section_key": "chief_complaint",
            "command_type": "rfv",
            "old_command_uuid": "rfv-uuid",
            "new_command_uuid": "rfv-uuid",
            "mode": "direct_edit",
            "display": "Headache",
        },
    ]
    mock_build.return_value = ([mock_effect], attempted)
    # Simulate the production query's actual return type: ``UUID``-like
    # objects whose hash differs from ``hash(str(uid))``. If the session
    # view ever stops coercing with ``str(...)`` and reverts to ``dict(...)``
    # of the raw tuples, this test bombs with HTTPStatus.CONFLICT +
    # ``command_not_found`` - the exact UAT failure mode.
    mock_command.objects.filter.return_value.values_list.return_value = [
        (_StubUUID("rfv-uuid"), "staged"),
    ]

    view = _helper_instance()
    commands = [
        {
            "command_type": "rfv",
            "command_uuid": "rfv-uuid",
            "section_key": "chief_complaint",
            "data": {"comment": "Headache"},
            "display": "Headache",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    result = view.post_edit_existing_commands()

    # The happy path must succeed - a regression here means the type
    # coercion is gone and every UAT amendment will 409 again.
    assert result[0].status_code == HTTPStatus.OK, (
        f"State-check must coerce UUID -> str so lookups by string command_uuid succeed; "
        f"got {result[0].status_code} with body {json.loads(result[0].content)!r}"
    )
    body = json.loads(result[0].content)
    assert "conflicts" not in body
    mock_build.assert_called_once_with(commands, "note-uuid-123")


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_edit_effects")
@patch("hyperscribe.scribe.api.session_view.Command")
def test_edit_existing_commands_audit_payload_excludes_display_phi(
    mock_command: MagicMock, mock_build: MagicMock, mock_audit: MagicMock
) -> None:
    """HIPAA regression: the AMEND_EXISTING_COMMANDS audit payload must NOT
    carry the ``display`` field. For HPI / ROS / PE / lab_results / current
    medications, ``display`` is free-text clinical narrative; persisting it
    into ``ScribeAuditLog.events`` is PHI in a log. Even 80-character truncation
    still leaks clinical content. The audit keeps only structural identifiers
    (section_key, command_type, uuids, mode).
    """
    mock_effect = MagicMock()
    attempted = [
        {
            "section_key": "history_of_present_illness",
            "command_type": "hpi",
            "old_command_uuid": "old-hpi-uuid",
            "new_command_uuid": "new-hpi-uuid",
            "mode": "void_recreate",
            "display": "Patient presents with 2 weeks of frontal headaches, worse with bright light",
        },
    ]
    mock_build.return_value = ([mock_effect], attempted)
    mock_command.objects.filter.return_value.values_list.return_value = [(_StubUUID("old-hpi-uuid"), "committed")]

    view = _helper_instance()
    commands = [
        {
            "command_type": "hpi",
            "command_uuid": "old-hpi-uuid",
            "section_key": "history_of_present_illness",
            "data": {"narrative": "Patient presents with 2 weeks of frontal headaches"},
            "display": "Patient presents with 2 weeks of frontal headaches, worse with bright light",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    view.post_edit_existing_commands()

    audit_calls = [c for c in mock_audit.call_args_list if c.args[1] == "AMEND_EXISTING_COMMANDS"]
    assert len(audit_calls) == 1
    payload = audit_calls[0].args[2]
    assert payload["entries"], "expected at least one entry to assert against"
    for entry in payload["entries"]:
        assert "display" not in entry, (
            f"AMEND_EXISTING_COMMANDS audit payload must not carry 'display' (PHI risk); got: {sorted(entry.keys())}"
        )
        assert set(entry.keys()) == {
            "section_key",
            "command_type",
            "old_command_uuid",
            "new_command_uuid",
            "mode",
        }


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_edit_effects")
@patch("hyperscribe.scribe.api.session_view.Command")
def test_edit_existing_commands_reads_state_before_emitting_effects(
    mock_command: MagicMock,
    mock_build: MagicMock,
    mock_audit: MagicMock,
) -> None:
    """The eligibility check must read Command.state via the plugin's view
    before deciding whether to emit effects. This pins the check-then-emit
    pattern - the common stale-tab case (Tab B submits after Tab A's EIE has
    landed) is caught here.

    There is NO atomic/row-lock guarantee at the plugin level: the sandbox
    bans ``from django.db import transaction`` (only ``from django.db
    .transaction import atomic`` is whitelisted), ``select_for_update()`` on
    the Command view fails at the SQL layer (FOR UPDATE on an outer-joined
    view), and the EnterInError effect is processed by home-app in its own
    transaction anyway. See the endpoint docstring for the residual race
    window and its visible artifact (duplicate Originate on near-simultaneous
    submits against a still-committed row).
    """
    mock_effect = MagicMock()
    attempted = [
        {
            "section_key": "history_of_present_illness",
            "command_type": "hpi",
            "old_command_uuid": "old-hpi-uuid",
            "new_command_uuid": "new-hpi-uuid",
            "mode": "void_recreate",
            "display": "narrative",
        },
    ]
    mock_build.return_value = ([mock_effect], attempted)

    mock_command.objects.filter.return_value.values_list.return_value = [(_StubUUID("old-hpi-uuid"), "committed")]

    view = _helper_instance()
    commands = [
        {
            "command_type": "hpi",
            "command_uuid": "old-hpi-uuid",
            "section_key": "history_of_present_illness",
            "data": {"narrative": "edit"},
            "display": "narrative",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    view.post_edit_existing_commands()

    # The Command query went through .filter() (the SDK-sandbox-compatible path).
    mock_command.objects.filter.assert_called_once()
    # And NOT through the no-longer-supported select_for_update() path.
    mock_command.objects.select_for_update.assert_not_called()
    # Happy path: build_amend_edit_effects was invoked (no conflict surfaced).
    mock_build.assert_called_once_with(commands, "note-uuid-123")


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_edit_effects")
@patch("hyperscribe.scribe.api.session_view.Command")
def test_amend_conflict_audit_payload_excludes_display_phi(
    mock_command: MagicMock, mock_build: MagicMock, mock_audit: MagicMock
) -> None:
    """HIPAA regression: the AMEND_CONFLICT audit payload must also not carry
    free-text clinical narrative. Conflicts are emitted on cross-tab races
    against committed/voided rows - same PHI surface area as the success path.
    The structured conflict shape (section_key, command_type, uuid, state,
    reason) is already PHI-free; this test pins that.
    """
    mock_command.objects.filter.return_value.values_list.return_value = [
        (_StubUUID("old-hpi-uuid"), "entered_in_error"),
    ]

    view = _helper_instance()
    commands = [
        {
            "command_type": "hpi",
            "command_uuid": "old-hpi-uuid",
            "section_key": "history_of_present_illness",
            "data": {"narrative": "Tab B stale narrative with PHI"},
            "display": "Patient reports severe abdominal pain radiating to right shoulder",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    view.post_edit_existing_commands()

    audit_calls = [c for c in mock_audit.call_args_list if c.args[1] == "AMEND_CONFLICT"]
    assert len(audit_calls) == 1
    payload = audit_calls[0].args[2]
    for conflict in payload["conflicts"]:
        assert "display" not in conflict, (
            f"AMEND_CONFLICT conflict entry must not carry 'display' (PHI risk); got: {sorted(conflict.keys())}"
        )
    # build_amend_edit_effects was not called - no effects emitted on conflict.
    mock_build.assert_not_called()


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_edit_effects")
@patch("hyperscribe.scribe.api.session_view.Command")
def test_amend_audit_payload_does_not_propagate_new_attempted_keys(
    mock_command: MagicMock, mock_build: MagicMock, mock_audit: MagicMock
) -> None:
    """HIPAA defense-in-depth: the AMEND_EXISTING_COMMANDS audit payload is built
    from a fixed key whitelist. If a future change adds a new key to the
    ``attempted`` records (e.g., the ``display`` field that was historically
    surfaced there), it must NOT silently propagate into the audit log.

    This test pins the whitelist mechanism: even when ``attempted`` carries a
    phantom ``_future_phi`` key (simulating a future record-shape regression),
    the audit entry only contains the structural identifiers.
    """
    mock_effect = MagicMock()
    attempted = [
        {
            "section_key": "history_of_present_illness",
            "command_type": "hpi",
            "old_command_uuid": "old-hpi-uuid",
            "new_command_uuid": "new-hpi-uuid",
            "mode": "void_recreate",
            "display": "free-text clinical narrative that must not leak",
            # Phantom key simulating a future record-shape regression.
            "_future_phi": "Patient reports severe abdominal pain (PHI)",
        },
    ]
    mock_build.return_value = ([mock_effect], attempted)
    mock_command.objects.filter.return_value.values_list.return_value = [(_StubUUID("old-hpi-uuid"), "committed")]

    view = _helper_instance()
    commands = [
        {
            "command_type": "hpi",
            "command_uuid": "old-hpi-uuid",
            "section_key": "history_of_present_illness",
            "data": {"narrative": "edit"},
            "display": "narrative",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    view.post_edit_existing_commands()

    audit_calls = [c for c in mock_audit.call_args_list if c.args[1] == "AMEND_EXISTING_COMMANDS"]
    assert len(audit_calls) == 1
    payload = audit_calls[0].args[2]
    assert payload["entries"], "expected at least one entry to assert against"
    expected_keys = {"section_key", "command_type", "old_command_uuid", "new_command_uuid", "mode"}
    for entry in payload["entries"]:
        actual_keys = set(entry.keys())
        assert actual_keys == expected_keys, (
            f"AMEND_EXISTING_COMMANDS audit entries must be built from the fixed whitelist "
            f"{sorted(expected_keys)}; got: {sorted(actual_keys)}. The dict comprehension "
            f"over a whitelist constant prevents new attempted-record keys from silently "
            f"leaking PHI into the audit log."
        )
        assert "_future_phi" not in entry
        assert "display" not in entry


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_edit_effects")
@patch("hyperscribe.scribe.api.session_view.Command")
def test_edit_existing_commands_audit_fires_after_state_check(
    mock_command: MagicMock,
    mock_build: MagicMock,
    mock_audit: MagicMock,
) -> None:
    """Ordering invariant: ``audit_event(AMEND_EXISTING_COMMANDS, ...)`` must
    fire AFTER the Command state read and ``build_amend_edit_effects`` call.

    Why this matters: ``audit_event()`` catches broad ``Exception`` via
    ``log.exception(...)`` so an audit-write failure cannot suppress the
    response or short-circuit effect emission. We pin the ordering so a
    future refactor can't accidentally hoist the audit above the state read
    (which would let an audit-side DB failure swallow the actual amendment).
    """
    mock_effect = MagicMock()
    attempted = [
        {
            "section_key": "history_of_present_illness",
            "command_type": "hpi",
            "old_command_uuid": "old-hpi-uuid",
            "new_command_uuid": "new-hpi-uuid",
            "mode": "void_recreate",
        },
    ]
    mock_build.return_value = ([mock_effect], attempted)
    mock_command.objects.filter.return_value.values_list.return_value = [(_StubUUID("old-hpi-uuid"), "committed")]

    # Record the order in which key collaborators are touched.
    call_log: list[str] = []

    def record_filter(*_args: Any, **_kwargs: Any) -> MagicMock:
        call_log.append("state_read")
        # Re-stage the chained mock so the production code keeps working.
        chained = MagicMock()
        chained.values_list.return_value = [(_StubUUID("old-hpi-uuid"), "committed")]
        return chained

    mock_command.objects.filter.side_effect = record_filter

    def record_build(*_args: Any, **_kwargs: Any) -> tuple[list[Any], list[dict[str, Any]]]:
        call_log.append("build_effects")
        return ([mock_effect], attempted)

    mock_build.side_effect = record_build

    def record_audit(*args: Any, **_kwargs: Any) -> None:
        if len(args) >= 2 and args[1] in ("AMEND_EXISTING_COMMANDS", "AMEND_CONFLICT"):
            call_log.append(f"audit:{args[1]}")

    mock_audit.side_effect = record_audit

    view = _helper_instance()
    commands = [
        {
            "command_type": "hpi",
            "command_uuid": "old-hpi-uuid",
            "section_key": "history_of_present_illness",
            "data": {"narrative": "edit"},
            "display": "narrative",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    view.post_edit_existing_commands()

    # State read came first, build_effects came second, audit came last.
    assert call_log == ["state_read", "build_effects", "audit:AMEND_EXISTING_COMMANDS"], (
        f"audit_event(AMEND_EXISTING_COMMANDS) must fire after the state read + effect emission step. Got: {call_log}"
    )


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_edit_effects")
@patch("hyperscribe.scribe.api.session_view.Command")
def test_amend_conflict_audit_fires_after_state_check(
    mock_command: MagicMock,
    mock_build: MagicMock,
    mock_audit: MagicMock,
) -> None:
    """Same ordering invariant for the AMEND_CONFLICT branch: the conflict
    audit must fire AFTER the state read decides the row is incompatible.
    ``build_amend_edit_effects`` must NOT have been called (conflicts short-
    circuit effect emission).
    """
    call_log: list[str] = []

    def record_filter(*_args: Any, **_kwargs: Any) -> MagicMock:
        call_log.append("state_read")
        chained = MagicMock()
        chained.values_list.return_value = [(_StubUUID("old-hpi-uuid"), "entered_in_error")]
        return chained

    mock_command.objects.filter.side_effect = record_filter

    def record_audit(*args: Any, **_kwargs: Any) -> None:
        if len(args) >= 2 and args[1] in ("AMEND_EXISTING_COMMANDS", "AMEND_CONFLICT"):
            call_log.append(f"audit:{args[1]}")

    mock_audit.side_effect = record_audit

    view = _helper_instance()
    commands = [
        {
            "command_type": "hpi",
            "command_uuid": "old-hpi-uuid",
            "section_key": "history_of_present_illness",
            "data": {"narrative": "edit"},
            "display": "Patient reports severe abdominal pain (PHI)",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    result = view.post_edit_existing_commands()

    assert result[0].status_code == HTTPStatus.CONFLICT
    # State read first, then audit. build_amend_edit_effects was not called.
    assert call_log == ["state_read", "audit:AMEND_CONFLICT"], (
        f"audit_event(AMEND_CONFLICT) must fire after the state read and conflicts must "
        f"short-circuit effect emission. Got: {call_log}"
    )
    mock_build.assert_not_called()


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


# --- /delete-existing-commands (KOALA-5485 charge-delete regression) ---


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_delete_effects")
@patch("hyperscribe.scribe.api.session_view.Command")
def test_delete_existing_commands_perform_eie_only(
    mock_command: MagicMock, mock_build: MagicMock, mock_audit: MagicMock
) -> None:
    """Charge delete during amend mode emits ENTER_IN_ERROR(old) only - no
    Originate, no Commit. The returned ``attempted`` carries ``command_uuid``
    (no new uuid to mint) and ``mode="amend_delete"`` so the frontend can
    filter it out of the working commands array before /insert-commands.
    """
    eie_effect = MagicMock()
    attempted = [
        {
            "section_key": "_charges_ad_hoc",
            "command_type": "perform",
            "command_uuid": "perform-uuid",
            "mode": "amend_delete",
        },
    ]
    mock_build.return_value = ([eie_effect], attempted)
    # State check: row is currently 'committed' - valid for delete (EIE only).
    mock_command.objects.filter.return_value.values_list.return_value = [
        (_StubUUID("perform-uuid"), "committed"),
    ]

    view = _helper_instance()
    commands = [
        {
            "command_type": "perform",
            "command_uuid": "perform-uuid",
            "section_key": "_charges_ad_hoc",
            "data": {"cpt_code": "99213", "description": "Office visit"},
            "display": "99213 - Office visit",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-abc", "commands": commands}))
    result = view.post_delete_existing_commands()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["attempted"] == attempted
    assert len(result) == 2  # JSONResponse + 1 EIE effect
    assert result[1] is eie_effect
    mock_build.assert_called_once_with(commands, "note-uuid-abc")
    mock_audit.assert_called_once()
    audit_call = mock_audit.call_args
    assert audit_call.args[0] == "note-uuid-abc"
    assert audit_call.args[1] == "AMEND_EXISTING_COMMANDS"
    payload = audit_call.args[2]
    assert payload["delete_count"] == 1
    assert payload["effect_count"] == 1
    assert payload["deleted"][0]["mode"] == "amend_delete"
    assert payload["deleted"][0]["command_uuid"] == "perform-uuid"
    # PHI guard: the audit payload must NOT carry ``display`` even when
    # build_amend_delete_effects omits it - belt-and-suspenders via the
    # ``_AMEND_AUDIT_ENTRY_KEYS`` whitelist.
    assert "display" not in payload["deleted"][0]


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_delete_effects")
@patch("hyperscribe.scribe.api.session_view.Command")
def test_delete_existing_commands_audit_payload_excludes_display_phi(
    mock_command: MagicMock, mock_build: MagicMock, mock_audit: MagicMock
) -> None:
    """Defense-in-depth: even if a future build_amend_delete_effects regression
    starts including ``display`` in the attempted records, the audit payload
    must NOT propagate it. The whitelist comprehension over
    ``_AMEND_AUDIT_ENTRY_KEYS`` filters out PHI before audit_event is called.

    Mirrors the AMEND_EXISTING_COMMANDS PHI hardening rationale.
    """
    # Build a malicious-future-shape attempted record carrying free-text
    # clinical narrative as ``display``. This is the regression we're guarding.
    leak_attempted = [
        {
            "section_key": "_charges_ad_hoc",
            "command_type": "perform",
            "command_uuid": "perform-uuid",
            "mode": "amend_delete",
            "display": "PHI-style narrative that must not appear in audit",
        },
    ]
    mock_build.return_value = ([MagicMock()], leak_attempted)
    mock_command.objects.filter.return_value.values_list.return_value = [
        (_StubUUID("perform-uuid"), "committed"),
    ]

    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note_uuid": "note-uuid-abc",
                "commands": [
                    {
                        "command_type": "perform",
                        "command_uuid": "perform-uuid",
                        "section_key": "_charges_ad_hoc",
                        "data": {"cpt_code": "99213"},
                        "display": "x",
                    }
                ],
            }
        )
    )
    view.post_delete_existing_commands()

    audit_call = mock_audit.call_args
    payload = audit_call.args[2]
    # The whitelist comprehension must have stripped ``display``.
    assert "display" not in payload["deleted"][0]
    # And the rest of the structural keys must survive.
    assert payload["deleted"][0]["section_key"] == "_charges_ad_hoc"
    assert payload["deleted"][0]["command_type"] == "perform"
    assert payload["deleted"][0]["mode"] == "amend_delete"


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_delete_effects")
@patch("hyperscribe.scribe.api.session_view.Command")
def test_delete_existing_commands_rejects_stale_amend_on_already_voided_row(
    mock_command: MagicMock, mock_build: MagicMock, mock_audit: MagicMock
) -> None:
    """Cross-tab concurrency: Tab A deletes perform X (X is now
    entered_in_error). Tab B (stale, still showing X checked) submits its
    own delete against X. Backend must reject Tab B with HTTP 409 so the
    frontend can prompt reload, NOT silently no-op.
    """
    mock_command.objects.filter.return_value.values_list.return_value = [
        (_StubUUID("perform-uuid"), "entered_in_error"),
    ]

    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note_uuid": "note-uuid-abc",
                "commands": [
                    {
                        "command_type": "perform",
                        "command_uuid": "perform-uuid",
                        "section_key": "_charges_ad_hoc",
                        "data": {"cpt_code": "99213"},
                        "display": "x",
                    }
                ],
            }
        )
    )
    result = view.post_delete_existing_commands()

    assert result[0].status_code == HTTPStatus.CONFLICT
    payload = json.loads(result[0].content)
    assert "conflicts" in payload
    assert payload["conflicts"][0]["reason"] == "state_mismatch_already_voided"
    # No effects emitted.
    assert len(result) == 1
    # build_amend_delete_effects was NOT called - we bailed before emission.
    mock_build.assert_not_called()
    # Audit fires AMEND_CONFLICT with the operation marker.
    audit_call = mock_audit.call_args
    assert audit_call.args[1] == "AMEND_CONFLICT"
    assert audit_call.args[2]["operation"] == "delete"


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_delete_effects")
@patch("hyperscribe.scribe.api.session_view.Command")
def test_delete_existing_commands_rejects_when_command_uuid_missing_from_db(
    mock_command: MagicMock, mock_build: MagicMock, mock_audit: MagicMock
) -> None:
    """If the underlying Command row doesn't exist (uuid never landed,
    originate was reverted, or stale frontend), surface a 409 rather than
    silently no-op. The user reloads to pick up the latest state.
    """
    # State lookup returns no rows.
    mock_command.objects.filter.return_value.values_list.return_value = []

    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note_uuid": "note-uuid-abc",
                "commands": [
                    {
                        "command_type": "perform",
                        "command_uuid": "ghost-uuid",
                        "section_key": "_charges_ad_hoc",
                        "data": {"cpt_code": "99213"},
                        "display": "x",
                    }
                ],
            }
        )
    )
    result = view.post_delete_existing_commands()

    assert result[0].status_code == HTTPStatus.CONFLICT
    payload = json.loads(result[0].content)
    assert payload["conflicts"][0]["reason"] == "command_not_found"
    mock_build.assert_not_called()


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_amend_delete_effects")
def test_delete_existing_commands_silently_drops_disallowed_section(
    mock_build: MagicMock, mock_audit: MagicMock
) -> None:
    """Sections not in EDITABLE_AMEND_SECTIONS are silently dropped (logged at
    WARN inside build_amend_delete_effects). No state lookup, no conflict.
    """
    mock_build.return_value = ([], [])

    view = _helper_instance()
    commands = [
        {
            "command_type": "perform",
            "command_uuid": "perform-uuid",
            "section_key": "_recommended",  # not in EDITABLE_AMEND_SECTIONS
            "data": {"cpt_code": "99213"},
            "display": "x",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-abc", "commands": commands}))
    result = view.post_delete_existing_commands()

    assert result[0].status_code == HTTPStatus.OK
    payload = json.loads(result[0].content)
    assert payload["attempted"] == []
    audit_call = mock_audit.call_args
    assert audit_call.args[1] == "AMEND_EXISTING_COMMANDS"
    assert audit_call.args[2]["delete_count"] == 0
    assert audit_call.args[2]["deleted"] == []


@patch("hyperscribe.scribe.api.session_view.audit_event")
def test_delete_existing_commands_silently_drops_missing_command_uuid(
    mock_audit: MagicMock,
) -> None:
    """An editable section without a command_uuid is silently dropped, not
    treated as a fresh insert. WARN logged inside build_amend_delete_effects.
    """
    view = _helper_instance()
    commands = [
        {
            "command_type": "perform",
            "section_key": "_charges_ad_hoc",
            "data": {"cpt_code": "99213"},
            "display": "x",
        },
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-abc", "commands": commands}))
    result = view.post_delete_existing_commands()

    assert result[0].status_code == HTTPStatus.OK
    payload = json.loads(result[0].content)
    assert payload["attempted"] == []


def test_delete_existing_commands_missing_note_uuid() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"commands": []}))
    result = view.post_delete_existing_commands()

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


def test_delete_existing_commands_invalid_json() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body="not-json")
    result = view.post_delete_existing_commands()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]
