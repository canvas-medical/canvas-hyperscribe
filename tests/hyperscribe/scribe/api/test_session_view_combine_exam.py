import json
import re
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from canvas_sdk.effects.simple_api import JSONResponse

from hyperscribe.scribe.api.session_view import ScribeSessionView

# Disable automatic route resolution (mirrors the other session_view tests).
ScribeSessionView._ROUTES = {}

TEMPLATE = [{"key": "general", "title": "General", "text": "Well-appearing."}]
CURRENT = [{"key": "general", "title": "General", "text": "Tender RLQ."}]
# reconcile_sections returns key/title/text plus updated/template_text — the endpoint strips the latter.
RECONCILED = [
    {"key": "general", "title": "General", "text": "Tender RLQ.", "updated": True, "template_text": "Well-appearing."}
]


def _view(secrets=None) -> ScribeSessionView:
    event = SimpleNamespace(context={"method": "POST"})
    view = ScribeSessionView(event, secrets if secrets is not None else {"AnthropicAPIKey": "sk-test"}, {})
    view._path_pattern = re.compile(r".*")
    view.request = SimpleNamespace(headers={"canvas-logged-in-user-id": "staff-1"}, query_params={}, body=b"")
    return view


def _with_body(view: ScribeSessionView, payload: dict) -> None:
    view.request = SimpleNamespace(headers={"canvas-logged-in-user-id": "staff-1"}, body=json.dumps(payload))


@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
@patch("hyperscribe.scribe.api.session_view.reconcile_sections", return_value=RECONCILED)
def test_combine_happy_physical_exam(mock_recon: MagicMock, _auth: MagicMock) -> None:
    view = _view()
    _with_body(
        view, {"note_id": "n1", "kind": "physical_exam", "template_sections": TEMPLATE, "current_sections": CURRENT}
    )
    result = view.post_combine_exam()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["merged"] is True
    # updated/template_text stripped — only key/title/text returned.
    assert data["sections"] == [{"key": "general", "title": "General", "text": "Tender RLQ."}]
    mock_recon.assert_called_once_with(TEMPLATE, CURRENT, "sk-test", "Physical Exam")


@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
@patch("hyperscribe.scribe.api.session_view.reconcile_sections", return_value=RECONCILED)
def test_combine_ros_label(mock_recon: MagicMock, _auth: MagicMock) -> None:
    view = _view()
    _with_body(view, {"note_id": "n1", "kind": "ros", "template_sections": TEMPLATE, "current_sections": CURRENT})
    view.post_combine_exam()
    mock_recon.assert_called_once_with(TEMPLATE, CURRENT, "sk-test", "Review of Systems")


@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
@patch("hyperscribe.scribe.api.session_view.reconcile_sections")
def test_combine_no_api_key_is_noop(mock_recon: MagicMock, _auth: MagicMock) -> None:
    view = _view(secrets={})  # no AnthropicAPIKey
    _with_body(
        view, {"note_id": "n1", "kind": "physical_exam", "template_sections": TEMPLATE, "current_sections": CURRENT}
    )
    result = view.post_combine_exam()

    data = json.loads(result[0].content)
    assert data["merged"] is False
    assert data["sections"] == CURRENT  # echoed back unchanged
    mock_recon.assert_not_called()  # never attempt the LLM without a key


@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
@patch("hyperscribe.scribe.api.session_view.reconcile_sections", return_value=None)
def test_combine_reconcile_failure_is_noop(mock_recon: MagicMock, _auth: MagicMock) -> None:
    view = _view()
    _with_body(
        view, {"note_id": "n1", "kind": "physical_exam", "template_sections": TEMPLATE, "current_sections": CURRENT}
    )
    result = view.post_combine_exam()

    data = json.loads(result[0].content)
    assert data["merged"] is False
    assert data["sections"] == CURRENT
    mock_recon.assert_called_once()


@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_combine_invalid_kind(_auth: MagicMock) -> None:
    view = _view()
    _with_body(view, {"note_id": "n1", "kind": "exam", "template_sections": TEMPLATE, "current_sections": CURRENT})
    result = view.post_combine_exam()
    assert result[0].status_code == HTTPStatus.BAD_REQUEST


def test_combine_invalid_json() -> None:
    view = _view()
    view.request = SimpleNamespace(headers={"canvas-logged-in-user-id": "staff-1"}, body="not json")
    result = view.post_combine_exam()
    assert result[0].status_code == HTTPStatus.BAD_REQUEST


@patch(
    "hyperscribe.scribe.api.session_view._authorize_edit",
    return_value=JSONResponse({"error": "nope"}, status_code=HTTPStatus.FORBIDDEN),
)
def test_combine_auth_denied(_auth: MagicMock) -> None:
    view = _view()
    _with_body(
        view, {"note_id": "n1", "kind": "physical_exam", "template_sections": TEMPLATE, "current_sections": CURRENT}
    )
    result = view.post_combine_exam()
    assert result[0].status_code == HTTPStatus.FORBIDDEN
