import json
import re
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from canvas_sdk.effects.simple_api import JSONResponse

from hyperscribe.scribe.api.session_view import ScribeSessionView, _last_exam_sections

# Disable automatic route resolution (mirrors test_session_view.py).
ScribeSessionView._ROUTES = {}

PE_SECTIONS = [{"key": "general", "title": "General", "text": "Well-appearing."}]
ROS_SECTIONS = [{"key": "constitutional", "title": "Constitutional", "text": "Denies fever."}]


def _view(staff_id: str = "staff-1") -> ScribeSessionView:
    event = SimpleNamespace(context={"method": "GET"})
    view = ScribeSessionView(event, {"ScribeBackend": "{}"}, {})
    view._path_pattern = re.compile(r".*")
    view.request = SimpleNamespace(
        headers={"canvas-logged-in-user-id": staff_id},
        query_params={},
        body=b"",
    )
    return view


def _summary_row(note_id: int, command_type: str = "physical_exam", sections=PE_SECTIONS) -> dict:
    return {"note_id": note_id, "commands": [{"command_type": command_type, "data": {"sections": sections}}]}


def _wire_prior_notes(mock_note: MagicMock, patient_id: str, dbids: list[int]) -> None:
    mock_note.objects.values_list.return_value.get.return_value = patient_id
    mock_note.objects.filter.return_value.exclude.return_value.order_by.return_value.values_list.return_value = dbids


# ── _last_exam_sections ──


@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_last_exam_happy_physical_exam(mock_note: MagicMock, mock_summary: MagicMock) -> None:
    _wire_prior_notes(mock_note, "patient-uuid", [10, 20])
    mock_summary.objects.filter.return_value.values.return_value = [_summary_row(10)]

    assert _last_exam_sections("note-uuid", "staff-1", "physical_exam") == PE_SECTIONS


@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_last_exam_happy_ros(mock_note: MagicMock, mock_summary: MagicMock) -> None:
    _wire_prior_notes(mock_note, "patient-uuid", [10])
    mock_summary.objects.filter.return_value.values.return_value = [
        _summary_row(10, command_type="ros", sections=ROS_SECTIONS)
    ]

    assert _last_exam_sections("note-uuid", "staff-1", "ros") == ROS_SECTIONS


@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_last_exam_returns_most_recent(mock_note: MagicMock, mock_summary: MagicMock) -> None:
    # dbids ordered most-recent first; both have a PE — the first (10) wins.
    _wire_prior_notes(mock_note, "patient-uuid", [10, 20])
    newer = [{"key": "general", "title": "General", "text": "Newer."}]
    older = [{"key": "general", "title": "General", "text": "Older."}]
    mock_summary.objects.filter.return_value.values.return_value = [
        _summary_row(20, sections=older),
        _summary_row(10, sections=newer),
    ]

    assert _last_exam_sections("note-uuid", "staff-1", "physical_exam") == newer


@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_last_exam_skips_note_without_matching_command(mock_note: MagicMock, mock_summary: MagicMock) -> None:
    # Most-recent note (10) has only an ROS; the PE lives on the older note (20).
    _wire_prior_notes(mock_note, "patient-uuid", [10, 20])
    mock_summary.objects.filter.return_value.values.return_value = [
        _summary_row(10, command_type="ros", sections=ROS_SECTIONS),
        _summary_row(20, command_type="physical_exam", sections=PE_SECTIONS),
    ]

    assert _last_exam_sections("note-uuid", "staff-1", "physical_exam") == PE_SECTIONS


@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_last_exam_empty_sections_skipped(mock_note: MagicMock, mock_summary: MagicMock) -> None:
    _wire_prior_notes(mock_note, "patient-uuid", [10])
    mock_summary.objects.filter.return_value.values.return_value = [_summary_row(10, sections=[])]

    assert _last_exam_sections("note-uuid", "staff-1", "physical_exam") == []


@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_last_exam_no_prior_notes(mock_note: MagicMock, mock_summary: MagicMock) -> None:
    _wire_prior_notes(mock_note, "patient-uuid", [])

    assert _last_exam_sections("note-uuid", "staff-1", "physical_exam") == []


@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_last_exam_no_summary_for_prior_notes(mock_note: MagicMock, mock_summary: MagicMock) -> None:
    _wire_prior_notes(mock_note, "patient-uuid", [10, 20])
    mock_summary.objects.filter.return_value.values.return_value = []

    assert _last_exam_sections("note-uuid", "staff-1", "physical_exam") == []


def test_last_exam_invalid_kind_short_circuits() -> None:
    # No DB access for an unknown kind.
    assert _last_exam_sections("note-uuid", "staff-1", "bogus") == []


def test_last_exam_missing_staff_short_circuits() -> None:
    assert _last_exam_sections("note-uuid", "", "physical_exam") == []


@patch("hyperscribe.scribe.api.session_view.Note")
def test_last_exam_note_not_found(mock_note: MagicMock) -> None:
    mock_note.DoesNotExist = ValueError
    mock_note.objects.values_list.return_value.get.side_effect = ValueError()

    assert _last_exam_sections("missing", "staff-1", "physical_exam") == []


@patch("hyperscribe.scribe.api.session_view.Note")
def test_last_exam_no_patient(mock_note: MagicMock) -> None:
    mock_note.objects.values_list.return_value.get.return_value = None

    assert _last_exam_sections("note-uuid", "staff-1", "physical_exam") == []


@patch("hyperscribe.scribe.api.session_view.Note")
def test_last_exam_prior_query_error_swallowed(mock_note: MagicMock) -> None:
    mock_note.objects.values_list.return_value.get.return_value = "patient-uuid"
    mock_note.objects.filter.return_value.exclude.return_value.order_by.return_value.values_list.side_effect = (
        RuntimeError("db blip")
    )

    assert _last_exam_sections("note-uuid", "staff-1", "physical_exam") == []


@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_last_exam_command_without_sections_skipped(mock_note: MagicMock, mock_summary: MagicMock) -> None:
    # Matching command_type but data is non-dict / missing / has no section list.
    _wire_prior_notes(mock_note, "patient-uuid", [10])
    mock_summary.objects.filter.return_value.values.return_value = [
        {
            "note_id": 10,
            "commands": [
                {"command_type": "physical_exam", "data": None},
                {"command_type": "physical_exam"},
                {"command_type": "physical_exam", "data": {"sections": "nope"}},
            ],
        },
    ]

    assert _last_exam_sections("note-uuid", "staff-1", "physical_exam") == []


@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_last_exam_malformed_commands_skipped(mock_note: MagicMock, mock_summary: MagicMock) -> None:
    _wire_prior_notes(mock_note, "patient-uuid", [10, 20])
    mock_summary.objects.filter.return_value.values.return_value = [
        {"note_id": 10, "commands": "not-a-list"},
        {
            "note_id": 20,
            "commands": ["not-a-dict", {"command_type": "physical_exam", "data": {"sections": PE_SECTIONS}}],
        },
    ]

    assert _last_exam_sections("note-uuid", "staff-1", "physical_exam") == PE_SECTIONS


# ── GET /last-exam endpoint ──


@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
@patch("hyperscribe.scribe.api.session_view._last_exam_sections", return_value=PE_SECTIONS)
def test_get_last_exam_success(mock_sections: MagicMock, _auth: MagicMock) -> None:
    view = _view()
    view.request = SimpleNamespace(
        headers={"canvas-logged-in-user-id": "staff-1"},
        query_params={"note_id": "n1", "kind": "physical_exam"},
    )
    result = view.get_last_exam()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content) == {"sections": PE_SECTIONS}
    mock_sections.assert_called_once_with("n1", "staff-1", "physical_exam")


@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_get_last_exam_invalid_kind(_auth: MagicMock) -> None:
    view = _view()
    view.request = SimpleNamespace(
        headers={"canvas-logged-in-user-id": "staff-1"},
        query_params={"note_id": "n1", "kind": "exam"},  # the official command key — rejected
    )
    result = view.get_last_exam()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST


@patch(
    "hyperscribe.scribe.api.session_view._authorize_edit",
    return_value=JSONResponse({"error": "nope"}, status_code=HTTPStatus.FORBIDDEN),
)
def test_get_last_exam_auth_denied(_auth: MagicMock) -> None:
    view = _view()
    view.request = SimpleNamespace(
        headers={"canvas-logged-in-user-id": "other"},
        query_params={"note_id": "n1", "kind": "physical_exam"},
    )
    result = view.get_last_exam()

    assert result[0].status_code == HTTPStatus.FORBIDDEN
