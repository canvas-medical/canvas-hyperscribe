from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

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
    """No zip codes provided → unfiltered call returns all results, sorted."""
    mock_http.get_json.return_value = _mock_science_response([_GENERIC_PSYCHIATRY_TBD, _LOCAL_PSYCHIATRIST])

    results = search_refer_providers("psychiatry")

    assert len(results) == 2
    # Sort must apply to the no-zip unfiltered path too — local before TBD even
    # though TBD came first from science.
    assert results[0]["data"]["last_name"] != "(TBD)"
    assert results[1]["data"]["last_name"] == "(TBD)"
    mock_http.get_json.assert_called_once_with("/contacts/?search=psychiatry")


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_fallback_unfiltered_still_sorts_local_first(mock_http: MagicMock) -> None:
    """When zip-filtered call returns empty AND fallback unfiltered runs, the
    sort must STILL apply so a TBD doesn't land in results[0] for a sparse-zip
    patient. Regression for the UAT-discovered bug where sort was only applied
    on the zip-filtered early-return path."""
    # First call (zip-filtered) returns empty; second call (unfiltered) returns
    # TBD first then local — the helper must reorder.
    mock_http.get_json.side_effect = [
        _mock_science_response([]),
        _mock_science_response([_GENERIC_PSYCHIATRY_TBD, _LOCAL_PSYCHIATRIST]),
    ]

    results = search_refer_providers("psychiatry", zip_codes=["87101"])

    assert len(results) == 2
    assert results[0]["data"]["last_name"] != "(TBD)", "local must come before TBD on fallback path"
    assert results[1]["data"]["last_name"] == "(TBD)"
    assert mock_http.get_json.call_count == 2


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


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_exception_log_does_not_leak_query_or_url(
    mock_http: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """HIPAA: the search query and request URL must NOT appear in failure logs.

    Patient identifiers ride in the typed search query (e.g. provider types a
    patient name when searching referrals). HTTPError messages embed the full
    URL — including the query string — so log.exception / str(exc) would leak
    it. The handler must log only the exception class name.
    """
    # Simulate the worst case: an HTTPError-style message that embeds the URL.
    sensitive_query = "PATIENTLASTNAME"
    mock_http.get_json.side_effect = RuntimeError(
        f"500 Server Error: Internal Server Error for url: https://science.example/contacts/?search={sensitive_query}"
    )

    with caplog.at_level(logging.ERROR, logger="plugin_runner_logger"):
        results = search_refer_providers(sensitive_query, zip_codes=["92591"])

    assert results == []
    combined = " ".join(rec.getMessage() for rec in caplog.records)
    assert sensitive_query not in combined, "search query (a potential PHI carrier) must not appear in error logs"
    assert "?search=" not in combined, "request URL substring must not appear in error logs"
    assert "/contacts/" not in combined, "request path must not appear in error logs"
    # Sanity: we should still record the exception class for diagnostics.
    assert any("RuntimeError" in rec.getMessage() for rec in caplog.records)


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
def test_search_imaging_centers_issues_one_call_per_specialty_filter(
    mock_http: MagicMock,
) -> None:
    """One call per imaging-adjacent specialty: radiology + nuclear medicine.

    The science FilterSet only exposes ``__icontains`` (no ``__in``/``__iregex``),
    so we issue one call per imaging-adjacent value and merge. ``radiology``
    catches both ``Radiology`` and ``Vascular & Interventional Radiology``;
    ``nuclear medicine`` catches the Nuclear Medicine specialty.
    """
    mock_http.get_json.return_value = _mock_science_response([_LOCAL_IMAGING_CENTER])

    search_imaging_centers("mri", zip_codes=["92591"])

    # Two specialty filters → two API calls, each carrying its own filter value.
    assert mock_http.get_json.call_count == 2
    call_urls = [call.args[0] for call in mock_http.get_json.call_args_list]
    for url in call_urls:
        assert "job_title__icontains" in url
    assert any("radiology" in url for url in call_urls)
    assert any("nuclear" in url for url in call_urls)


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_imaging_centers_specialty_filters_present_without_zip(
    mock_http: MagicMock,
) -> None:
    """Even without a zip-filter, both specialty filters scope unfiltered calls."""
    mock_http.get_json.return_value = _mock_science_response([_LOCAL_IMAGING_CENTER])

    search_imaging_centers("mri")

    assert mock_http.get_json.call_count == 2
    call_urls = [call.args[0] for call in mock_http.get_json.call_args_list]
    for url in call_urls:
        assert "job_title__icontains" in url
    assert any("radiology" in url for url in call_urls)
    assert any("nuclear" in url for url in call_urls)


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
    """No zip_codes → one unfiltered call per specialty filter (two total)."""
    mock_http.get_json.return_value = _mock_science_response([_LOCAL_IMAGING_CENTER, _GENERIC_IMAGING_TBD])

    results = search_imaging_centers("radiology", zip_codes=None)

    # Identical mock results from both specialty calls collapse to 2 after dedup.
    assert len(results) == 2
    # Two unfiltered calls — one per specialty filter, no postal_code filter on either.
    assert mock_http.get_json.call_count == 2
    for call in mock_http.get_json.call_args_list:
        assert "business_postal_code__in" not in call.args[0]


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_imaging_centers_falls_back_when_zip_returns_empty(
    mock_http: MagicMock,
) -> None:
    """When the zip-filtered call returns nothing, an unfiltered call is retried.

    Preserves the prior fallback semantics on the imaging-center endpoint:
    if a patient's zip has no nearby center matching the query, surface the
    generic + remote centers rather than returning an empty list. With two
    specialty filters and a fallback per filter, the worst case is 4 calls.
    """
    mock_http.get_json.side_effect = [
        # radiology specialty: zip-filtered empty → fall back to unfiltered
        _mock_science_response([]),
        _mock_science_response([_LOCAL_IMAGING_CENTER, _GENERIC_IMAGING_TBD]),
        # nuclear medicine specialty: zip-filtered empty → fall back to unfiltered
        _mock_science_response([]),
        _mock_science_response([_LOCAL_IMAGING_CENTER, _GENERIC_IMAGING_TBD]),
    ]

    results = search_imaging_centers("radiology", zip_codes=["99999"])

    # Two specialty calls × (zip + fallback) = 4 calls. Dedup collapses
    # repeated content from each specialty back to the original 2 contacts.
    assert len(results) == 2
    assert mock_http.get_json.call_count == 4


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
def test_search_imaging_centers_one_call_per_specialty_when_results_found(
    mock_http: MagicMock,
) -> None:
    """One zip-filtered call per specialty (no fallback) when each returns results."""
    mock_http.get_json.return_value = _mock_science_response([_LOCAL_IMAGING_CENTER, _GENERIC_IMAGING_TBD])

    search_imaging_centers("radiology", zip_codes=["92591"])

    # Two specialty filters, each returns results → no fallback fires.
    assert mock_http.get_json.call_count == 2


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_imaging_centers_exception_returns_empty(mock_http: MagicMock) -> None:
    """Network/API failure swallows the exception and returns an empty list."""
    mock_http.get_json.side_effect = Exception("Network error")

    results = search_imaging_centers("radiology", zip_codes=["92591"])

    assert results == []


# A real Nuclear Medicine provider — the gap that motivated the
# multi-specialty filter. The science FilterSet only supports __icontains,
# and "radiology" alone does not match the "Nuclear Medicine" job_title.
_NUCLEAR_MEDICINE_PROVIDER = {
    "firstName": "Hans",
    "lastName": "Geiger",
    "practiceName": "Pacific Nuclear Imaging",
    "specialty": "Nuclear Medicine",
    "businessPhone": "555-7777",
    "businessFax": "",
    "businessAddress": "300 Atomic Way, Temecula CA 92591",
}


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_imaging_centers_finds_nuclear_medicine_specialty(
    mock_http: MagicMock,
) -> None:
    """Nuclear Medicine providers must surface — they're invisible to "radiology" alone.

    Closes the gap where a provider ordering a PET scan would not find Nuclear
    Medicine specialists because the prior icontains=radiology filter excluded
    them at the science-service layer.
    """

    def side_effect(url: str) -> MagicMock:
        # Radiology bucket returns nothing for this query.
        if "icontains=radiology" in url or "icontains=Radiology" in url:
            return _mock_science_response([])
        # Nuclear medicine bucket returns the actual provider.
        return _mock_science_response([_NUCLEAR_MEDICINE_PROVIDER])

    mock_http.get_json.side_effect = side_effect

    results = search_imaging_centers("PET scan", zip_codes=["92591"])

    assert len(results) == 1
    assert "Hans" in results[0]["name"]
    assert results[0]["data"]["specialty"] == "Nuclear Medicine"


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_imaging_centers_merges_radiology_and_nuclear_medicine(
    mock_http: MagicMock,
) -> None:
    """Both specialty buckets contribute to the merged result set."""

    def side_effect(url: str) -> MagicMock:
        if "radiology" in url.lower():
            return _mock_science_response([_LOCAL_IMAGING_CENTER])
        return _mock_science_response([_NUCLEAR_MEDICINE_PROVIDER])

    mock_http.get_json.side_effect = side_effect

    results = search_imaging_centers("imaging", zip_codes=["92591"])

    names = [r["name"] for r in results]
    assert any("Temecula Radiology Group" in n for n in names)
    assert any("Hans" in n for n in names)
    assert len(results) == 2


@patch("hyperscribe.scribe.contacts.science_http")
def test_search_imaging_centers_dedupes_overlap_between_buckets(
    mock_http: MagicMock,
) -> None:
    """A contact returned by both specialty buckets is deduped, not duplicated.

    In practice each contact has exactly one job_title and the two icontains
    buckets are disjoint, but defensive dedup matters: if a future science-service
    behavior (e.g. a synthetic "Radiology / Nuclear Medicine" specialty) returns
    the same contact under both queries, we must not surface it twice.
    """
    # Both calls return the same single contact.
    mock_http.get_json.return_value = _mock_science_response([_LOCAL_IMAGING_CENTER])

    results = search_imaging_centers("radiology", zip_codes=["92591"])

    assert len(results) == 1
    assert "Temecula Radiology Group" in results[0]["name"]
