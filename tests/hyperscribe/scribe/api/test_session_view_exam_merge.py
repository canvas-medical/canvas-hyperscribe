"""Provider-initiated merge of a visit template's exam scaffold into one card.

Generation no longer merges anything, so these exercise the on-demand path: the
endpoint's gating and refusal reasons, the template lookup, and the single-kind merge
helper that stamps the undo reference copies and the audit payload. No Nabla or
Anthropic round trip.
"""

import json
import re
from http import HTTPStatus
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from canvas_sdk.effects.simple_api import JSONResponse

from hyperscribe.scribe.api.session_view import (
    ScribeSessionView,
    _clean_template_sections,
    _merge_exam_kind,
    _merge_note_sections,
    _resolve_merge_template,
)

# Disable automatic route resolution (mirrors test_session_view.py).
ScribeSessionView._ROUTES = {}

PE_TEMPLATE = [{"key": "general", "title": "General", "text": "Well-appearing."}]
ROS_TEMPLATE = [{"key": "constitutional", "title": "Constitutional", "text": "Denies fever."}]
MSE_TEMPLATE = [{"key": "mood", "title": "Mood", "text": "Euthymic."}]
CARD = [{"key": "general", "title": "General", "text": "Ill."}]

TEMPLATES = [
    {
        "name": "Subsequent Visit",
        "pe_sections": PE_TEMPLATE,
        "ros_sections": ROS_TEMPLATE,
        "mse_sections": None,
        "is_psychiatry": False,
    },
    {
        "name": "Psychiatry",
        "pe_sections": None,
        "ros_sections": ROS_TEMPLATE,
        "mse_sections": MSE_TEMPLATE,
        "is_psychiatry": True,
    },
]


def _merged(title: str = "General", text: str = "Ill.", updated: bool = True) -> list[dict[str, Any]]:
    return [
        {"key": title.lower(), "title": title, "text": text, "updated": updated, "template_text": "Well-appearing."}
    ]


def _view(secrets: dict[str, str] | None = None, body: dict[str, Any] | None = None) -> ScribeSessionView:
    base = {"ScribeBackend": "{}", "ScribeExamTemplateMerge": "ros,physical_exam,mental_status_exam"}
    base.update(secrets or {})
    event = SimpleNamespace(context={"method": "POST"})
    view = ScribeSessionView(event, base, {})
    view._path_pattern = re.compile(r".*")
    view.request = SimpleNamespace(
        headers={"canvas-logged-in-user-id": "staff-1"},
        query_params={},
        body=json.dumps(body if body is not None else {}).encode(),
    )
    return view


def _post(view: ScribeSessionView) -> tuple[int, dict[str, Any]]:
    result = view.post_merge_exam_template()
    assert len(result) == 1
    return result[0].status_code, json.loads(result[0].content)


# ── the single-kind merge helper ──


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_merge_returns_sections_and_both_restore_points(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    sections = _merged()
    mock_reconcile.return_value = (sections, True)
    data = _merge_exam_kind("physical_exam", PE_TEMPLATE, CARD, note_uuid="n1", api_key="key")
    assert data is not None
    assert data["sections"] == sections
    assert data["encounter_sections"] == CARD
    assert data["reconciled_sections"] == sections
    assert data["template_removed"] is False


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_restore_points_are_independent_copies(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    """Undo restores from these, so a later edit to ``sections`` must not alias in."""
    sections = _merged()
    mock_reconcile.return_value = (sections, True)
    data = _merge_exam_kind("physical_exam", PE_TEMPLATE, CARD, note_uuid="n1", api_key="key")
    assert data is not None
    data["sections"][0]["text"] = "rewritten"
    assert data["reconciled_sections"][0]["text"] == "Ill."
    assert data["encounter_sections"][0]["text"] == "Ill."


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_card_sections_are_what_gets_merged(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    """The card's current content is the merge input, so provider edits are respected."""
    mock_reconcile.return_value = (_merged(), True)
    edited = [{"key": "general", "title": "General", "text": "Provider typed this."}]
    _merge_exam_kind(
        "physical_exam", PE_TEMPLATE, edited, note_uuid="n1", api_key="key", note_sections=[{"key": "hpi"}]
    )
    args, kwargs = mock_reconcile.call_args
    assert args[0] == PE_TEMPLATE
    assert args[1] == edited
    assert args[3] == "Physical Exam"
    assert kwargs["note_sections"] == [{"key": "hpi"}]


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_failed_merge_returns_none_and_audits(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    mock_reconcile.return_value = ([], False)
    assert _merge_exam_kind("ros", ROS_TEMPLATE, CARD, note_uuid="n1", api_key="key") is None
    mock_audit.assert_called_once_with("n1", "TEMPLATE_MERGE_SKIPPED", {"kind": "ros", "reason": "llm_failed"})


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_missing_api_key_audits_no_api_key(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    mock_reconcile.return_value = ([], False)
    assert _merge_exam_kind("ros", ROS_TEMPLATE, CARD, note_uuid="n1", api_key="") is None
    mock_audit.assert_called_once_with("n1", "TEMPLATE_MERGE_SKIPPED", {"kind": "ros", "reason": "no_api_key"})


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_reconciled_audit_payload(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    mock_reconcile.return_value = (
        [
            {
                "title": "General",
                "text": "Ill.",
                "updated": True,
                "clauses": [
                    {"text": "Ill.", "provenance": "encounter"},
                    {"text": "Well developed.", "provenance": "template"},
                ],
            },
            {"title": "Skin", "text": "No rashes.", "updated": False, "clauses": []},
        ],
        True,
    )
    _merge_exam_kind("physical_exam", PE_TEMPLATE, CARD, note_uuid="n1", api_key="key")
    mock_audit.assert_called_once_with(
        "n1",
        "TEMPLATE_RECONCILED",
        {
            "kind": "physical_exam",
            "template_section_count": 1,
            "encounter_section_count": 1,
            "updated_count": 1,
            "template_clause_count": 1,
        },
    )


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_no_audit_payload_carries_section_text(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    """Audit rows are counts only. Exam text is PHI and must never land in the log."""
    mock_reconcile.return_value = (_merged(text="tender right shoulder"), True)
    _merge_exam_kind("physical_exam", PE_TEMPLATE, CARD, note_uuid="n1", api_key="key")
    assert "tender right shoulder" not in json.dumps(mock_audit.call_args[0][2])


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_merge_still_runs_without_a_note_uuid(mock_reconcile: MagicMock, mock_audit: MagicMock) -> None:
    mock_reconcile.return_value = (_merged(), True)
    assert _merge_exam_kind("physical_exam", PE_TEMPLATE, CARD, note_uuid="", api_key="key") is not None
    mock_audit.assert_not_called()


def test_clean_template_sections_coerces_and_filters() -> None:
    raw = [{"key": 1, "title": None, "text": 2}, "nope", {"title": "Skin"}]
    assert _clean_template_sections(raw) == [
        {"key": "1", "title": "None", "text": "2"},
        {"key": "", "title": "Skin", "text": ""},
    ]
    assert _clean_template_sections("nope") == []
    assert _clean_template_sections(None) == []


# ── resolving which template to merge ──


@patch("hyperscribe.scribe.api.session_view._load_templates", return_value=TEMPLATES)
def test_resolve_template_by_requested_name(mock_load: MagicMock) -> None:
    tmpl = _resolve_merge_template({}, "n1", "Psychiatry")
    assert tmpl is not None and tmpl["is_psychiatry"] is True


@patch("hyperscribe.scribe.api.session_view._load_templates", return_value=TEMPLATES)
def test_resolve_template_ignores_an_unknown_name(mock_load: MagicMock) -> None:
    """A hostile body can pick another configured template but cannot inject exam text."""
    assert _resolve_merge_template({}, "n1", "Attacker Template") is None


@patch("hyperscribe.scribe.api.session_view._saved_template_name", return_value="Subsequent Visit")
@patch("hyperscribe.scribe.api.session_view._load_templates", return_value=TEMPLATES)
def test_resolve_template_falls_back_to_the_saved_name(mock_load: MagicMock, mock_saved: MagicMock) -> None:
    """The autosave can lag a click, so an absent name is read off the summary row."""
    tmpl = _resolve_merge_template({}, "n1", "")
    assert tmpl is not None and tmpl["name"] == "Subsequent Visit"


@patch("hyperscribe.scribe.api.session_view._saved_template_name", return_value="")
@patch("hyperscribe.scribe.api.session_view._load_templates", return_value=TEMPLATES)
def test_resolve_template_none_when_no_name_anywhere(mock_load: MagicMock, mock_saved: MagicMock) -> None:
    assert _resolve_merge_template({}, "n1", None) is None


@patch("hyperscribe.scribe.api.session_view.Note")
@patch("hyperscribe.scribe.api.session_view.ScribeSummary")
def test_merge_note_sections_projects_key_and_text(mock_summary: MagicMock, mock_note: MagicMock) -> None:
    mock_note.objects.values_list.return_value.get.return_value = 7
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = {
        "note_data": {"sections": [{"key": "hpi", "title": "HPI", "text": "Shoulder pain."}, "junk"]}
    }
    assert _merge_note_sections("n1") == [{"key": "hpi", "text": "Shoulder pain."}]


@patch("hyperscribe.scribe.api.session_view.Note")
def test_merge_note_sections_swallows_a_query_error(mock_note: MagicMock) -> None:
    mock_note.objects.values_list.return_value.get.side_effect = RuntimeError("boom")
    assert _merge_note_sections("n1") == []


# ── the endpoint ──


def test_endpoint_rejects_bad_json() -> None:
    view = _view()
    view.request.body = b"{not json"
    status, payload = _post(view)
    assert status == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in payload["error"]


@patch(
    "hyperscribe.scribe.api.session_view._authorize_edit",
    return_value=JSONResponse({"error": "nope"}, status_code=HTTPStatus.FORBIDDEN),
)
def test_endpoint_passes_the_auth_denial_through(mock_auth: MagicMock) -> None:
    status, payload = _post(_view(body={"note_id": "n1", "kind": "physical_exam"}))
    assert status == HTTPStatus.FORBIDDEN
    assert payload == {"error": "nope"}


@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_endpoint_rejects_an_unknown_kind(mock_auth: MagicMock) -> None:
    status, payload = _post(_view(body={"note_id": "n1", "kind": "exam"}))
    assert status == HTTPStatus.BAD_REQUEST
    assert payload == {"error": "invalid kind"}


@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_endpoint_refuses_a_kind_the_secret_does_not_enable(mock_auth: MagicMock) -> None:
    view = _view({"ScribeExamTemplateMerge": "ros"}, {"note_id": "n1", "kind": "physical_exam"})
    status, payload = _post(view)
    assert status == HTTPStatus.OK
    assert payload == {"merged": False, "reason": "not_enabled"}


@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_endpoint_off_switch_refuses_everything(mock_auth: MagicMock) -> None:
    view = _view({"ScribeExamTemplateMerge": ""}, {"note_id": "n1", "kind": "ros"})
    assert _post(view)[1] == {"merged": False, "reason": "not_enabled"}


@patch("hyperscribe.scribe.api.session_view._saved_template_name", return_value="")
@patch("hyperscribe.scribe.api.session_view._load_templates", return_value=TEMPLATES)
@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_endpoint_refuses_when_the_note_has_no_template(
    mock_auth: MagicMock, mock_load: MagicMock, mock_saved: MagicMock
) -> None:
    status, payload = _post(_view(body={"note_id": "n1", "kind": "physical_exam"}))
    assert payload == {"merged": False, "reason": "no_template"}


@patch("hyperscribe.scribe.api.session_view._load_templates", return_value=TEMPLATES)
@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_endpoint_refuses_mse_on_a_non_psychiatry_template(mock_auth: MagicMock, mock_load: MagicMock) -> None:
    body = {"note_id": "n1", "kind": "mental_status_exam", "selected_template_name": "Subsequent Visit"}
    assert _post(_view(body=body))[1] == {"merged": False, "reason": "not_psychiatry"}


@patch("hyperscribe.scribe.api.session_view._load_templates", return_value=TEMPLATES)
@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_endpoint_refuses_when_the_template_has_no_exam_for_the_kind(
    mock_auth: MagicMock, mock_load: MagicMock
) -> None:
    body = {"note_id": "n1", "kind": "physical_exam", "selected_template_name": "Psychiatry"}
    assert _post(_view(body=body))[1] == {"merged": False, "reason": "no_template_exam"}


@patch("hyperscribe.scribe.api.session_view._merge_note_sections", return_value=[])
@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections", return_value=([], False))
@patch("hyperscribe.scribe.api.session_view._load_templates", return_value=TEMPLATES)
@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_endpoint_reports_a_failed_merge(
    mock_auth: MagicMock,
    mock_load: MagicMock,
    mock_reconcile: MagicMock,
    mock_audit: MagicMock,
    mock_notes: MagicMock,
) -> None:
    """200 with a reason, not a 5xx: the provider waited on this and is owed a sentence."""
    body = {
        "note_id": "n1",
        "kind": "physical_exam",
        "sections": CARD,
        "selected_template_name": "Subsequent Visit",
    }
    status, payload = _post(_view({"AnthropicAPIKey": "key"}, body))
    assert status == HTTPStatus.OK
    assert payload == {"merged": False, "reason": "merge_failed"}


@patch("hyperscribe.scribe.api.session_view._merge_note_sections", return_value=[{"key": "hpi", "text": "Pain."}])
@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
@patch("hyperscribe.scribe.api.session_view._load_templates", return_value=TEMPLATES)
@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_endpoint_success_returns_sections_and_restore_points(
    mock_auth: MagicMock,
    mock_load: MagicMock,
    mock_reconcile: MagicMock,
    mock_audit: MagicMock,
    mock_notes: MagicMock,
) -> None:
    sections = _merged()
    mock_reconcile.return_value = (sections, True)
    body = {
        "note_id": "n1",
        "kind": "physical_exam",
        "sections": CARD,
        "selected_template_name": "Subsequent Visit",
    }
    status, payload = _post(_view({"AnthropicAPIKey": "key"}, body))
    assert status == HTTPStatus.OK
    assert payload["merged"] is True
    assert payload["sections"] == sections
    assert payload["encounter_sections"] == CARD
    assert payload["reconciled_sections"] == sections
    assert payload["template_removed"] is False
    # The scaffold comes from the secret, never from the body.
    assert mock_reconcile.call_args[0][0] == PE_TEMPLATE
    assert mock_reconcile.call_args[0][1] == CARD
    assert mock_reconcile.call_args[1]["note_sections"] == [{"key": "hpi", "text": "Pain."}]


@patch("hyperscribe.scribe.api.session_view._merge_note_sections", return_value=[])
@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
@patch("hyperscribe.scribe.api.session_view._load_templates", return_value=TEMPLATES)
@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_endpoint_merges_an_empty_card(
    mock_auth: MagicMock,
    mock_load: MagicMock,
    mock_reconcile: MagicMock,
    mock_audit: MagicMock,
    mock_notes: MagicMock,
) -> None:
    """A card with nothing in it is a legitimate merge: the template becomes the exam."""
    mock_reconcile.return_value = (PE_TEMPLATE, True)
    body = {"note_id": "n1", "kind": "physical_exam", "sections": [], "selected_template_name": "Subsequent Visit"}
    status, payload = _post(_view({"AnthropicAPIKey": "key"}, body))
    assert status == HTTPStatus.OK
    assert payload["merged"] is True
    assert mock_reconcile.call_args[0][1] == []


@patch("hyperscribe.scribe.api.session_view._load_templates", return_value=TEMPLATES)
@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_endpoint_rejects_malformed_sections(mock_auth: MagicMock, mock_load: MagicMock) -> None:
    body = {
        "note_id": "n1",
        "kind": "physical_exam",
        "sections": ["not a dict"],
        "selected_template_name": "Subsequent Visit",
    }
    status, payload = _post(_view(body=body))
    assert status == HTTPStatus.BAD_REQUEST
    assert payload == {"error": "malformed sections"}
