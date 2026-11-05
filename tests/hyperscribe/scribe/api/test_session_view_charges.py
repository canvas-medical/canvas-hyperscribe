import json
import re
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from hyperscribe.scribe.api.session_view import ScribeSessionView

# Disable automatic route resolution
ScribeSessionView._ROUTES = {}


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


def test_search_charges_empty_query() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"query": ""})
    result = view.get_search_charges()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["results"] == []


def test_search_charges_missing_query() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={})
    result = view.get_search_charges()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["results"] == []


def test_search_charges_whitespace_only() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"query": "   "})
    result = view.get_search_charges()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["results"] == []


@patch("hyperscribe.scribe.api.session_view.ChargeDescriptionMaster")
def test_search_charges_by_code(mock_cdm: MagicMock) -> None:
    mock_record = MagicMock()
    mock_record.cpt_code = "99213"
    mock_record.short_name = "Office visit est"
    mock_record.name = "Office or other outpatient visit, established patient"

    mock_qs = MagicMock()
    mock_qs.exclude.return_value = mock_qs
    mock_qs.order_by.return_value.__getitem__ = MagicMock(return_value=[mock_record])
    mock_cdm.objects.filter.return_value = mock_qs

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"query": "992"})
    result = view.get_search_charges()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert len(data["results"]) == 1
    assert data["results"][0]["cpt_code"] == "99213"
    assert data["results"][0]["short_name"] == "Office visit est"
    assert data["results"][0]["full_name"] == "Office or other outpatient visit, established patient"


@patch("hyperscribe.scribe.api.session_view.ChargeDescriptionMaster")
def test_search_charges_by_name(mock_cdm: MagicMock) -> None:
    mock_record = MagicMock()
    mock_record.cpt_code = "99342"
    mock_record.short_name = "Home visit new"
    mock_record.name = "Home visit new patient"

    mock_qs = MagicMock()
    mock_qs.exclude.return_value = mock_qs
    mock_qs.order_by.return_value.__getitem__ = MagicMock(return_value=[mock_record])
    mock_cdm.objects.filter.return_value = mock_qs

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"query": "home visit"})
    result = view.get_search_charges()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert len(data["results"]) == 1
    assert data["results"][0]["cpt_code"] == "99342"
    assert data["results"][0]["short_name"] == "Home visit new"


@patch("hyperscribe.scribe.api.session_view.ChargeDescriptionMaster")
def test_search_charges_excludes_codes(mock_cdm: MagicMock) -> None:
    mock_record = MagicMock()
    mock_record.cpt_code = "99214"
    mock_record.short_name = "Office visit est mod"
    mock_record.name = "Office visit established moderate"

    mock_qs = MagicMock()
    mock_qs.exclude.return_value = mock_qs
    mock_qs.order_by.return_value.__getitem__ = MagicMock(return_value=[mock_record])
    mock_cdm.objects.filter.return_value = mock_qs

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"query": "992", "exclude": "99213,99215"})
    result = view.get_search_charges()

    assert result[0].status_code == HTTPStatus.OK
    mock_qs.exclude.assert_called_once_with(cpt_code__in=["99213", "99215"])
    data = json.loads(result[0].content)
    assert len(data["results"]) == 1


@patch("hyperscribe.scribe.api.session_view.ChargeDescriptionMaster")
def test_search_charges_empty_results(mock_cdm: MagicMock) -> None:
    mock_qs = MagicMock()
    mock_qs.exclude.return_value = mock_qs
    mock_qs.order_by.return_value.__getitem__ = MagicMock(return_value=[])
    mock_cdm.objects.filter.return_value = mock_qs

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"query": "xyznonexistent"})
    result = view.get_search_charges()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["results"] == []


from unittest.mock import MagicMock as _MagicMock
from canvas_sdk.effects import Effect


def _post_instance(body: dict, staff_id="staff-key-abc") -> ScribeSessionView:
    view = _helper_instance(staff_id)
    view.request = SimpleNamespace(
        headers={"canvas-logged-in-user-id": staff_id},
        query_params={},
        body=json.dumps(body).encode(),
    )
    return view


@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_charge_enrichment_effects")
def test_enrich_charges_happy_path(mock_build, mock_audit, mock_auth):
    effect = _MagicMock(spec=Effect)
    mock_build.return_value = (
        [effect],
        [{"command_uuid": "c1", "billing_line_item_id": "b1", "assessment_ids": ["a1"], "modifiers": ["25"]}],
        [],
    )
    view = _post_instance(
        {
            "note_uuid": "note-1",
            "charges": [
                {
                    "command_uuid": "c1",
                    "diagnosis_pointers": [{"command_uuid": "d1", "icd10_code": "M25.511"}],
                    "modifiers": ["25"],
                }
            ],
        }
    )
    result = view.post_enrich_charges()

    body = json.loads(result[0].content)  # JSONResponse first, then effects
    assert effect in result
    assert body["enriched"][0]["billing_line_item_id"] == "b1"
    assert body["errors"] == []
    mock_audit.assert_called_once()


@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_charge_enrichment_effects")
def test_enrich_charges_accepts_charge_without_pointer(mock_build, mock_audit, mock_auth):
    # Zero-pointer charges are advisory-only; the backend emits a clear effect
    # (no error) so sign is never blocked. Covers advisory-only new charges and
    # amendment unlink-all.
    mock_build.return_value = (
        [],
        [{"command_uuid": "c1", "billing_line_item_id": "b1", "assessment_ids": [], "modifiers": []}],
        [],
    )
    view = _post_instance(
        {
            "note_uuid": "note-1",
            "charges": [{"command_uuid": "c1", "diagnosis_pointers": [], "modifiers": []}],
        }
    )
    result = view.post_enrich_charges()
    assert result[0].status_code == HTTPStatus.OK
    body = json.loads(result[0].content)
    assert body["errors"] == []


def test_enrich_charges_requires_auth():
    # No _authorize_edit patch: real auth runs and short-circuits on missing note_uuid.
    view = _post_instance({"note_uuid": "", "charges": []})
    result = view.post_enrich_charges()
    assert result[0].status_code == HTTPStatus.BAD_REQUEST


def test_enrich_charges_invalid_json():
    view = _helper_instance()
    view.request = SimpleNamespace(headers={"canvas-logged-in-user-id": "x"}, query_params={}, body=b"not json")
    result = view.post_enrich_charges()
    assert result[0].status_code == HTTPStatus.BAD_REQUEST


@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_charge_enrichment_effects")
def test_enrich_charges_returns_200_with_partial_errors(mock_build, mock_audit, mock_auth):
    effect = _MagicMock(spec=Effect)
    mock_build.return_value = (
        [effect],
        [{"command_uuid": "ok", "billing_line_item_id": "b1", "assessment_ids": ["a1"], "modifiers": []}],
        [{"command_uuid": "bad", "reason": "billing_line_item_not_found"}],
    )
    view = _post_instance(
        {
            "note_uuid": "note-1",
            "charges": [
                {
                    "command_uuid": "ok",
                    "diagnosis_pointers": [{"command_uuid": "d1", "icd10_code": "M25.511"}],
                    "modifiers": [],
                },
                {
                    "command_uuid": "bad",
                    "diagnosis_pointers": [{"command_uuid": "d2", "icd10_code": "K21.9"}],
                    "modifiers": [],
                },
            ],
        }
    )
    result = view.post_enrich_charges()
    assert result[0].status_code == HTTPStatus.OK
    body = json.loads(result[0].content)
    assert body["errors"] == [{"command_uuid": "bad", "reason": "billing_line_item_not_found"}]
    assert effect in result


@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.build_charge_enrichment_effects")
def test_enrich_charges_passes_removed_charges_through(mock_build, mock_audit, mock_auth):
    mock_build.return_value = ([], [], [])
    view = _post_instance({"note_uuid": "note-1", "charges": [], "removed_charges": ["uuid-x"]})
    view.post_enrich_charges()
    args, kwargs = mock_build.call_args
    # signature: build_charge_enrichment_effects(charges, removed_command_uuids, note_uuid)
    assert args[1] == ["uuid-x"] or kwargs.get("removed_command_uuids") == ["uuid-x"] or args[0:3][1] == ["uuid-x"]
