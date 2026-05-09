from __future__ import annotations

from unittest.mock import MagicMock, patch

from hyperscribe.scribe.contacts import (
    _format_contact,
    search_refer_providers,
)


# -- Raw science-service contact fixtures --

_LOCAL_PSYCHIATRIST = {
    "firstName": "Jane",
    "lastName": "Smith",
    "practiceName": "Temecula Psych",
    "specialty": "Psychiatry",
    "businessPhone": "555-1234",
    "businessFax": "555-5678",
    "businessAddress": "100 Main St, Temecula CA 92591",
}

_GENERIC_PSYCHIATRY_TBD = {
    "firstName": "Psychiatry",
    "lastName": "TBD",
    "practiceName": "",
    "specialty": "Psychiatry",
    "businessPhone": "1111",
    "businessFax": "",
    "businessAddress": "1111",
}

_REMOTE_PSYCHIATRIST = {
    "firstName": "Bob",
    "lastName": "Jones",
    "practiceName": "LA Psych Group",
    "specialty": "Psychiatry",
    "businessPhone": "555-9999",
    "businessFax": "",
    "businessAddress": "200 Wilshire Blvd, Los Angeles CA 90001",
}


# -- _format_contact tests --


def test_format_contact_full():
    result = _format_contact(_LOCAL_PSYCHIATRIST)
    assert result["name"] == "Jane Smith (Temecula Psych), Psychiatry"
    assert "Phone: 555-1234" in result["description"]
    assert "Fax: 555-5678" in result["description"]
    assert result["data"]["first_name"] == "Jane"
    assert result["data"]["specialty"] == "Psychiatry"


def test_format_contact_generic():
    result = _format_contact(_GENERIC_PSYCHIATRY_TBD)
    assert "Psychiatry" in result["name"]
    assert "TBD" in result["name"]


# -- search_refer_providers tests --


def _mock_science_response(results):
    """Create a mock response object with .json() returning the given results."""
    mock = MagicMock()
    mock.json.return_value = {"results": results}
    return mock


def test_search_empty_query():
    assert search_refer_providers("") == []


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_no_zip_returns_all(mock_http):
    mock_http.get_json.return_value = _mock_science_response(
        [_LOCAL_PSYCHIATRIST, _GENERIC_PSYCHIATRY_TBD]
    )

    results = search_refer_providers("psychiatry")

    assert len(results) == 2
    mock_http.get_json.assert_called_once_with("/contacts/?search=psychiatry")


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_with_zip_includes_1111(mock_http):
    """Zip-filtered search should include '1111' postal code to capture generics."""
    mock_http.get_json.return_value = _mock_science_response(
        [_LOCAL_PSYCHIATRIST, _GENERIC_PSYCHIATRY_TBD]
    )

    results = search_refer_providers("psychiatry", zip_codes=["92591"])

    assert len(results) == 2
    # Verify the API was called with both the patient zip AND the generic postal code.
    mock_http.get_json.assert_called_once_with(
        "/contacts/?search=psychiatry&business_postal_code__in=92591,1111"
    )
    names = [r["name"] for r in results]
    assert any("Jane Smith" in n for n in names)
    assert any("TBD" in n for n in names)


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_with_zip_no_results_falls_back(mock_http):
    """When zip-filtered returns empty, unfiltered search is used."""
    mock_http.get_json.side_effect = [
        _mock_science_response([]),  # zip+1111 filtered: nothing
        _mock_science_response([_REMOTE_PSYCHIATRIST, _GENERIC_PSYCHIATRY_TBD]),  # unfiltered
    ]

    results = search_refer_providers("psychiatry", zip_codes=["99999"])

    assert len(results) == 2
    names = [r["name"] for r in results]
    assert any("Bob Jones" in n for n in names)
    assert any("TBD" in n for n in names)
    # Two calls: zip-filtered (empty), then unfiltered fallback
    assert mock_http.get_json.call_count == 2


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_with_zip_deduplicates_1111(mock_http):
    """If zip_codes already contains '1111', it shouldn't appear twice."""
    mock_http.get_json.return_value = _mock_science_response(
        [_GENERIC_PSYCHIATRY_TBD]
    )

    results = search_refer_providers("psychiatry", zip_codes=["1111"])

    assert len(results) == 1
    mock_http.get_json.assert_called_once_with(
        "/contacts/?search=psychiatry&business_postal_code__in=1111"
    )


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_single_api_call_when_results_found(mock_http):
    """When zip+1111 filter returns results, only one API call is made."""
    mock_http.get_json.return_value = _mock_science_response(
        [_LOCAL_PSYCHIATRIST, _GENERIC_PSYCHIATRY_TBD]
    )

    search_refer_providers("psychiatry", zip_codes=["92591"])

    assert mock_http.get_json.call_count == 1


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_exception_returns_empty(mock_http):
    mock_http.get_json.side_effect = Exception("Network error")

    results = search_refer_providers("psychiatry", zip_codes=["92591"])

    assert results == []
