from __future__ import annotations

from unittest.mock import MagicMock, patch

from hyperscribe.scribe.contacts import (
    _format_contact,
    _is_generic_contact,
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

_GENERIC_CARDIOLOGY_TBD = {
    "firstName": "Cardiology",
    "lastName": "TBD",
    "practiceName": "",
    "specialty": "Cardiology",
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


# -- _is_generic_contact tests --


def test_is_generic_contact_with_1111_address():
    assert _is_generic_contact(_GENERIC_PSYCHIATRY_TBD) is True


def test_is_generic_contact_with_normal_address():
    assert _is_generic_contact(_LOCAL_PSYCHIATRIST) is False


def test_is_generic_contact_with_empty_address():
    assert _is_generic_contact({"businessAddress": ""}) is False


def test_is_generic_contact_with_no_address_key():
    assert _is_generic_contact({}) is False


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
def test_search_with_zip_merges_generic(mock_http):
    """When zip-filtered results exist, generic contacts from the unfiltered
    search should be merged in."""
    mock_http.get_json.side_effect = [
        _mock_science_response([_LOCAL_PSYCHIATRIST]),  # zip-filtered
        _mock_science_response([_LOCAL_PSYCHIATRIST, _GENERIC_PSYCHIATRY_TBD, _REMOTE_PSYCHIATRIST]),  # unfiltered
    ]

    results = search_refer_providers("psychiatry", zip_codes=["92591"])

    assert len(results) == 2  # local + generic TBD (remote excluded)
    names = [r["name"] for r in results]
    assert any("Jane Smith" in n for n in names)
    assert any("TBD" in n for n in names)
    assert not any("Bob Jones" in n for n in names)


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_with_zip_no_local_results_falls_back(mock_http):
    """When zip-filtered returns empty, all unfiltered results are returned."""
    mock_http.get_json.side_effect = [
        _mock_science_response([]),  # zip-filtered: nothing local
        _mock_science_response([_REMOTE_PSYCHIATRIST, _GENERIC_PSYCHIATRY_TBD]),  # unfiltered
    ]

    results = search_refer_providers("psychiatry", zip_codes=["99999"])

    assert len(results) == 2
    names = [r["name"] for r in results]
    assert any("Bob Jones" in n for n in names)
    assert any("TBD" in n for n in names)


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_with_zip_no_duplicates(mock_http):
    """Generic contacts already in local results are not duplicated."""
    mock_http.get_json.side_effect = [
        _mock_science_response([_LOCAL_PSYCHIATRIST, _GENERIC_PSYCHIATRY_TBD]),  # zip-filtered includes generic
        _mock_science_response([_GENERIC_PSYCHIATRY_TBD, _REMOTE_PSYCHIATRIST]),  # unfiltered
    ]

    results = search_refer_providers("psychiatry", zip_codes=["92591"])

    # Local (Jane) + Generic TBD (already in local, not duped) = 2
    assert len(results) == 2
    tbd_count = sum(1 for r in results if "TBD" in r["name"])
    assert tbd_count == 1


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_with_zip_multiple_generics(mock_http):
    """Multiple generic contacts are all merged in."""
    mock_http.get_json.side_effect = [
        _mock_science_response([_LOCAL_PSYCHIATRIST]),  # zip-filtered
        _mock_science_response([_GENERIC_PSYCHIATRY_TBD, _GENERIC_CARDIOLOGY_TBD, _REMOTE_PSYCHIATRIST]),  # unfiltered
    ]

    results = search_refer_providers("psych", zip_codes=["92591"])

    assert len(results) == 3  # local + psych TBD + cardiology TBD
    names = [r["name"] for r in results]
    assert any("Jane Smith" in n for n in names)
    assert any("Psychiatry" in n and "TBD" in n for n in names)
    assert any("Cardiology" in n and "TBD" in n for n in names)


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_exception_returns_empty(mock_http):
    mock_http.get_json.side_effect = Exception("Network error")

    results = search_refer_providers("psychiatry", zip_codes=["92591"])

    assert results == []
