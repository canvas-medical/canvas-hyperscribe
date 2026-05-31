from __future__ import annotations

from unittest.mock import MagicMock, patch

from hyperscribe.scribe.contacts import (
    _format_contact,
    _is_generic,
    search_imaging_centers,
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

# Mirrors how science-service marks generic contacts at import time:
# `last_name = "(TBD)"` with parentheses. The serializer omits
# `business_postal_code` from the response, so it's not present here.
_GENERIC_PSYCHIATRY_TBD = {
    "firstName": "Psychiatry",
    "lastName": "(TBD)",
    "practiceName": "",
    "specialty": "Psychiatry",
    "businessPhone": "",
    "businessFax": "",
    "businessAddress": "11111",
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

# Real provider whose street address starts with "11111" — would have been
# misclassified as generic under the old substring-match sort key.
_LOCAL_PROVIDER_AT_11111_MAIN = {
    "firstName": "Alice",
    "lastName": "Cooper",
    "practiceName": "11111 Main Medical",
    "specialty": "Psychiatry",
    "businessPhone": "555-1111",
    "businessFax": "",
    "businessAddress": "11111 Main St, Temecula CA 92591",
}


# -- _format_contact tests --


def test_format_contact_full():
    result = _format_contact(_LOCAL_PSYCHIATRIST)
    assert result["name"] == "Jane Smith (Temecula Psych), Psychiatry"
    assert "Phone: 555-1234" in result["description"]
    assert "Fax: 555-5678" in result["description"]
    assert result["data"]["first_name"] == "Jane"
    assert result["data"]["specialty"] == "Psychiatry"


def test_format_contact_generic() -> None:
    """Generic TBD entries should still produce a recognizable display name."""
    result = _format_contact(_GENERIC_PSYCHIATRY_TBD)
    assert "Psychiatry" in result["name"]
    assert "TBD" in result["name"]


# -- _is_generic tests --


def test_is_generic_recognizes_tbd_lastname() -> None:
    """`lastName == "(TBD)"` is the canonical sentinel science-service uses."""
    assert _is_generic(_GENERIC_PSYCHIATRY_TBD) is True


def test_is_generic_rejects_real_provider_with_11111_in_address() -> None:
    """A real provider at "11111 Main St" must NOT be classified as generic.

    Closes the substring false-positive: the prior sort key (`"11111" in
    businessAddress`) flagged this entry as generic and demoted it.
    """
    assert _is_generic(_LOCAL_PROVIDER_AT_11111_MAIN) is False


def test_is_generic_rejects_normal_provider() -> None:
    """A normal local provider is not generic."""
    assert _is_generic(_LOCAL_PSYCHIATRIST) is False


def test_is_generic_handles_missing_lastname() -> None:
    """Contacts with missing or null lastName must not crash and are non-generic."""
    assert _is_generic({"firstName": "Smith"}) is False
    assert _is_generic({"lastName": None}) is False
    assert _is_generic({"lastName": ""}) is False


def test_is_generic_strips_whitespace() -> None:
    """Leading/trailing whitespace around "(TBD)" must still resolve as generic."""
    assert _is_generic({"lastName": " (TBD) "}) is True


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
    mock_http.get_json.return_value = _mock_science_response([_LOCAL_PSYCHIATRIST, _GENERIC_PSYCHIATRY_TBD])

    results = search_refer_providers("psychiatry")

    assert len(results) == 2
    mock_http.get_json.assert_called_once_with("/contacts/?search=psychiatry")


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_with_zip_includes_11111(mock_http):
    """Zip-filtered search should include '11111' postal code to capture generics."""
    mock_http.get_json.return_value = _mock_science_response([_LOCAL_PSYCHIATRIST, _GENERIC_PSYCHIATRY_TBD])

    results = search_refer_providers("psychiatry", zip_codes=["92591"])

    assert len(results) == 2
    # Verify URL-encoded params with both patient zip and generic postal codes.
    call_url = mock_http.get_json.call_args[0][0]
    assert "search=psychiatry" in call_url
    assert "business_postal_code__in=" in call_url
    assert "92591" in call_url
    assert "11111" in call_url
    # Import script also writes "." for rows missing business_postal_code.
    assert "%2C." in call_url or ",." in call_url


# Generic TBD referral provider using "." as the import-script fallback for
# customer-supplied CSV rows that omitted business_postal_code.
_GENERIC_PSYCHIATRY_TBD_DOT = {
    "firstName": "Psychiatry",
    "lastName": "(TBD)",
    "practiceName": "",
    "specialty": "Psychiatry",
    "businessPhone": "",
    "businessFax": "",
    "businessAddress": ".",
}


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_refer_providers_tbd_with_dot_postal_visible(mock_http: MagicMock) -> None:
    """TBD referral providers imported with the "." fallback postal must surface."""
    mock_http.get_json.return_value = _mock_science_response([_GENERIC_PSYCHIATRY_TBD_DOT])

    results = search_refer_providers("psychiatry", zip_codes=["92591"])

    assert len(results) == 1
    assert "Psychiatry" in results[0]["name"]
    assert "TBD" in results[0]["name"]


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_with_zip_local_providers_sorted_first(mock_http: MagicMock) -> None:
    """Local providers should appear before generic TBD entries in results."""
    # Science service returns generic before local
    mock_http.get_json.return_value = _mock_science_response([_GENERIC_PSYCHIATRY_TBD, _LOCAL_PSYCHIATRIST])

    results = search_refer_providers("psychiatry", zip_codes=["92591"])

    assert len(results) == 2
    # results[0] should be the real local provider, not the TBD
    assert "Jane Smith" in results[0]["name"]
    assert "TBD" in results[1]["name"]


@patch("hyperscribe.scribe.contacts.science_http")
def test_sort_local_before_generic_handles_real_address_containing_11111(
    mock_http: MagicMock,
) -> None:
    """A real provider at '11111 Main St' must still sort before a TBD entry.

    Regression for the substring-match false positive: the old sort key
    treated "11111" appearing anywhere in businessAddress as generic, so
    a real provider at a street number starting with 11111 was demoted
    behind the placeholder. The structural `lastName == "(TBD)"` check
    avoids that conflation.
    """
    # Science service returns the TBD first; the real "11111 Main St" provider
    # second. Under the old sort key the real provider would have been sorted
    # AFTER the TBD (both treated as generic). Under the new key only the
    # actual TBD is generic, so it gets demoted as expected.
    mock_http.get_json.return_value = _mock_science_response([_GENERIC_PSYCHIATRY_TBD, _LOCAL_PROVIDER_AT_11111_MAIN])

    results = search_refer_providers("psychiatry", zip_codes=["92591"])

    assert len(results) == 2
    assert "Alice Cooper" in results[0]["name"], (
        "Real provider with '11111' in street address must sort before TBD placeholder"
    )
    assert "TBD" in results[1]["name"]


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_with_zip_no_results_falls_back(mock_http):
    """When zip-filtered returns empty, unfiltered search is used."""
    mock_http.get_json.side_effect = [
        _mock_science_response([]),  # zip+11111 filtered: nothing
        _mock_science_response([_REMOTE_PSYCHIATRIST, _GENERIC_PSYCHIATRY_TBD]),  # unfiltered
    ]

    results = search_refer_providers("psychiatry", zip_codes=["99999"])

    assert len(results) == 2
    names = [r["name"] for r in results]
    assert any("Bob Jones" in n for n in names)
    assert any("TBD" in n for n in names)
    assert mock_http.get_json.call_count == 2


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_with_zip_deduplicates_11111(mock_http):
    """If zip_codes already contains '11111', it shouldn't appear twice."""
    mock_http.get_json.return_value = _mock_science_response([_GENERIC_PSYCHIATRY_TBD])

    results = search_refer_providers("psychiatry", zip_codes=["11111"])

    assert len(results) == 1
    call_url = mock_http.get_json.call_args[0][0]
    # 11111 should only appear once in the URL
    assert call_url.count("11111") == 1


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_single_api_call_when_results_found(mock_http):
    """When zip+11111 filter returns results, only one API call is made."""
    mock_http.get_json.return_value = _mock_science_response([_LOCAL_PSYCHIATRIST, _GENERIC_PSYCHIATRY_TBD])

    search_refer_providers("psychiatry", zip_codes=["92591"])

    assert mock_http.get_json.call_count == 1


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_url_encodes_query(mock_http):
    """Query with special characters should be URL-encoded."""
    mock_http.get_json.return_value = _mock_science_response([])

    search_refer_providers("ENT & Allergy", zip_codes=["92591"])

    call_url = mock_http.get_json.call_args[0][0]
    # & should be encoded, not treated as a param separator
    assert "ENT+%26+Allergy" in call_url or "ENT+%26" in call_url


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_exception_returns_empty(mock_http):
    mock_http.get_json.side_effect = Exception("Network error")

    results = search_refer_providers("psychiatry", zip_codes=["92591"])

    assert results == []


# -- search_imaging_centers tests --

_LOCAL_IMAGING_CENTER = {
    "firstName": "",
    "lastName": "",
    "practiceName": "Temecula Radiology Group",
    "specialty": "Radiology",
    "businessPhone": "555-2222",
    "businessFax": "555-3333",
    "businessAddress": "200 Center Dr, Temecula CA 92591",
}

# Generic imaging-center placeholder ("Grove Diagnostic Imaging TBD Radiology")
# using lastName="(TBD)" — the canonical sentinel science-service marks at
# import time. Used to exercise the missing-imaging-center surfacing path.
_GENERIC_IMAGING_TBD = {
    "firstName": "Grove Diagnostic Imaging",
    "lastName": "(TBD)",
    "practiceName": "",
    "specialty": "Radiology",
    "businessPhone": "",
    "businessFax": "",
    "businessAddress": "11111",
}


def test_search_imaging_centers_empty_query() -> None:
    """Empty query short-circuits without an API call."""
    assert search_imaging_centers("") == []


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_imaging_centers_with_zip_includes_11111(mock_http: MagicMock) -> None:
    """Zip-filtered imaging-center search must include '11111' so TBD centers surface.

    Without including the generic '11111' placeholder postal code alongside the
    patient's zip, generic TBD imaging centers (e.g. "Grove Diagnostic Imaging
    TBD Radiology") disappear for any patient whose zip does not match '11111'.
    """
    mock_http.get_json.return_value = _mock_science_response([_LOCAL_IMAGING_CENTER, _GENERIC_IMAGING_TBD])

    results = search_imaging_centers("radiology", zip_codes=["92591"])

    assert len(results) == 2
    call_url = mock_http.get_json.call_args[0][0]
    assert "search=radiology" in call_url
    assert "business_postal_code__in=" in call_url
    assert "92591" in call_url
    assert "11111" in call_url
    # The import script also writes "." as the fallback for rows missing
    # business_postal_code, so the filter must include it too.
    assert "%2C." in call_url or ",." in call_url


# Generic TBD imaging center using "." as the import-script fallback for a
# customer-supplied CSV row that omitted business_postal_code.
_GENERIC_IMAGING_TBD_DOT = {
    "firstName": "Coastal Imaging",
    "lastName": "(TBD)",
    "practiceName": "",
    "specialty": "Radiology",
    "businessPhone": "",
    "businessFax": "",
    "businessAddress": ".",
}


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_imaging_centers_tbd_with_dot_postal_visible(mock_http: MagicMock) -> None:
    """TBD imaging centers imported with the "." fallback postal must surface.

    The science import command writes "." into business_postal_code when a
    customer-supplied CSV row omits the column. Without "." in the zip filter,
    those generic contacts vanish for any patient whose zip is not literally ".".
    """
    mock_http.get_json.return_value = _mock_science_response([_GENERIC_IMAGING_TBD_DOT])

    results = search_imaging_centers("radiology", zip_codes=["92591"])

    assert len(results) == 1
    assert "Coastal Imaging" in results[0]["name"]
    assert "TBD" in results[0]["name"]


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_imaging_centers_preserves_radiology_filter(mock_http: MagicMock) -> None:
    """The job_title__icontains=radiology filter must be sent on every call."""
    mock_http.get_json.return_value = _mock_science_response([_LOCAL_IMAGING_CENTER])

    search_imaging_centers("mri", zip_codes=["92591"])

    call_url = mock_http.get_json.call_args[0][0]
    # urlencode encodes the dunder filter key directly; just check the
    # parameter and value appear (allowing either raw or percent-encoded).
    assert "job_title__icontains" in call_url
    assert "radiology" in call_url


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_imaging_centers_radiology_filter_present_without_zip(
    mock_http: MagicMock,
) -> None:
    """Even without a zip-filter, the radiology filter must scope unfiltered calls."""
    mock_http.get_json.return_value = _mock_science_response([_LOCAL_IMAGING_CENTER])

    search_imaging_centers("mri")

    call_url = mock_http.get_json.call_args[0][0]
    assert "job_title__icontains" in call_url
    assert "radiology" in call_url


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_imaging_centers_local_sorted_before_generic(
    mock_http: MagicMock,
) -> None:
    """A local imaging center must appear before a TBD center."""
    # Science service returns the TBD first to verify sort actually happens.
    mock_http.get_json.return_value = _mock_science_response([_GENERIC_IMAGING_TBD, _LOCAL_IMAGING_CENTER])

    results = search_imaging_centers("radiology", zip_codes=["92591"])

    assert len(results) == 2
    assert "Temecula Radiology Group" in results[0]["name"]
    assert "TBD" in results[1]["name"]


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_imaging_centers_url_encodes_query(mock_http: MagicMock) -> None:
    """Query with special characters must be URL-encoded, not split on &."""
    mock_http.get_json.return_value = _mock_science_response([])

    search_imaging_centers("MRI & CT", zip_codes=["92591"])

    call_url = mock_http.get_json.call_args[0][0]
    # & must be encoded (%26), not act as a param separator.
    assert "MRI" in call_url
    assert "%26" in call_url


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_imaging_centers_empty_zip_falls_through(mock_http: MagicMock) -> None:
    """No zip_codes → unfiltered call (single API call), still with radiology filter."""
    mock_http.get_json.return_value = _mock_science_response([_LOCAL_IMAGING_CENTER, _GENERIC_IMAGING_TBD])

    results = search_imaging_centers("radiology", zip_codes=None)

    assert len(results) == 2
    assert mock_http.get_json.call_count == 1
    call_url = mock_http.get_json.call_args[0][0]
    # No postal_code filter on this path.
    assert "business_postal_code__in" not in call_url


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_imaging_centers_falls_back_when_zip_returns_empty(
    mock_http: MagicMock,
) -> None:
    """When zip+11111 returns nothing, an unfiltered radiology call is retried.

    Preserves the prior fallback semantics on the imaging-center endpoint:
    if a patient's zip has no nearby center matching the query, surface the
    generic + remote centers rather than returning an empty list.
    """
    mock_http.get_json.side_effect = [
        _mock_science_response([]),  # zip+11111 filtered: nothing
        _mock_science_response([_LOCAL_IMAGING_CENTER, _GENERIC_IMAGING_TBD]),  # unfiltered
    ]

    results = search_imaging_centers("radiology", zip_codes=["99999"])

    assert len(results) == 2
    assert mock_http.get_json.call_count == 2


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_imaging_centers_tbd_visible_for_non_matching_zip(
    mock_http: MagicMock,
) -> None:
    """A TBD imaging center must surface even when the patient's zip is different.

    Regression: TBD centers must remain visible for patients whose zip does not
    match the placeholder's. Including '11111' in the zip filter restores that
    result.
    """
    mock_http.get_json.return_value = _mock_science_response([_GENERIC_IMAGING_TBD])

    results = search_imaging_centers("radiology", zip_codes=["92591"])

    assert len(results) == 1
    assert "Grove Diagnostic Imaging" in results[0]["name"]
    assert "TBD" in results[0]["name"]


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_imaging_centers_single_call_when_results_found(
    mock_http: MagicMock,
) -> None:
    """Single API call when zip+11111 returns results — no duplicate request."""
    mock_http.get_json.return_value = _mock_science_response([_LOCAL_IMAGING_CENTER, _GENERIC_IMAGING_TBD])

    search_imaging_centers("radiology", zip_codes=["92591"])

    assert mock_http.get_json.call_count == 1


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_imaging_centers_exception_returns_empty(mock_http: MagicMock) -> None:
    """Network/API failure swallows the exception and returns an empty list."""
    mock_http.get_json.side_effect = Exception("Network error")

    results = search_imaging_centers("radiology", zip_codes=["92591"])

    assert results == []
