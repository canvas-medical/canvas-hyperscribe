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
def test_search_charges_empty_results(mock_cdm: MagicMock) -> None:
    mock_qs = MagicMock()
    mock_qs.order_by.return_value.__getitem__ = MagicMock(return_value=[])
    mock_cdm.objects.filter.return_value = mock_qs

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"query": "xyznonexistent"})
    result = view.get_search_charges()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["results"] == []
