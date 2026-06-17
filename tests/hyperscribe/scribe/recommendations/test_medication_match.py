from __future__ import annotations

from unittest.mock import MagicMock, patch

from hyperscribe.scribe.recommendations._medication_match import (
    extract_strengths,
    resolve_medication_detail,
    sanitize_sig,
    select_medication,
)
from hyperscribe.structures.medication_detail import MedicationDetail


def _detail(fdb_code: str, description: str) -> MedicationDetail:
    return MedicationDetail(fdb_code=fdb_code, description=description, quantities=[])


def test_extract_strengths_normalizes_units_and_spacing() -> None:
    assert extract_strengths("Lisinopril 20 mg tablet") == {"20mg"}
    assert extract_strengths("Lisinopril 20mg") == {"20mg"}
    assert extract_strengths("Lisinopril 20 MG") == {"20mg"}
    assert extract_strengths("Levothyroxine 0.5 mcg") == {"0.5mcg"}


def test_extract_strengths_no_strength() -> None:
    assert extract_strengths("Lisinopril") == set()
    assert extract_strengths("") == set()


def test_extract_strengths_combination_product() -> None:
    # combination strengths split into one token per component, sharing the unit
    assert extract_strengths("Lisinopril-HCTZ 20-12.5 mg tablet") == {"20mg", "12.5mg"}
    assert extract_strengths("Symbicort 160/4.5 mcg") == {"160mcg", "4.5mcg"}
    # and FDB's split rendering of the same product yields the same tokens
    assert extract_strengths("Symbicort 160 mcg-4.5 mcg/actuation HFA") == {"160mcg", "4.5mcg"}


def test_extract_strengths_comma_thousands_separator() -> None:
    assert extract_strengths("metformin 1,000 mg tablet") == {"1000mg"}
    assert extract_strengths("metformin 1000 mg") == {"1000mg"}
    # stated and FDB-formatted strengths normalize to the same token
    assert extract_strengths("metformin 1000 mg").issubset(extract_strengths("metformin 1,000 mg tablet"))


def test_extract_strengths_folds_units_plural() -> None:
    # "2000 units" (stated) and "2,000 unit" (FDB) must match
    assert extract_strengths("vitamin D 2000 units") == {"2000unit"}
    assert extract_strengths("Vitamin D3 50 mcg (2,000 unit) tablet") == {"50mcg", "2000unit"}
    assert extract_strengths("vitamin D 2000 units").issubset(
        extract_strengths("Vitamin D3 50 mcg (2,000 unit) tablet")
    )


def test_select_medication_matches_combination_and_comma() -> None:
    candidates = [
        _detail("x", "metformin 500 mg tablet"),
        _detail("y", "metformin 1,000 mg tablet"),
    ]
    assert select_medication("metformin 1000 mg", candidates).fdb_code == "y"

    combo = [
        _detail("mono", "budesonide 160 mcg inhaler"),
        _detail("combo", "Symbicort 160 mcg-4.5 mcg/actuation HFA aerosol inhaler"),
    ]
    assert select_medication("Symbicort 160/4.5 mcg", combo).fdb_code == "combo"


def test_extract_strengths_distinguishes_similar_numbers() -> None:
    # "20 mg" must not be considered present in "120 mg" or "2.5 mg"
    assert extract_strengths("Lisinopril 120 mg") == {"120mg"}
    assert "20mg" not in extract_strengths("Lisinopril 120 mg")


def test_select_medication_prefers_stated_strength() -> None:
    candidates = [
        _detail("10", "Lisinopril 10 mg Tablet"),
        _detail("20", "Lisinopril 20 mg Tablet"),
    ]
    chosen = select_medication("Lisinopril 20 mg", candidates)
    assert chosen is not None
    assert chosen.fdb_code == "20"


def test_select_medication_falls_back_to_first() -> None:
    candidates = [
        _detail("10", "Lisinopril 10 mg Tablet"),
        _detail("40", "Lisinopril 40 mg Tablet"),
    ]
    # no candidate carries 5 mg -> first candidate
    chosen = select_medication("Lisinopril 5 mg", candidates)
    assert chosen is not None
    assert chosen.fdb_code == "10"


def test_select_medication_no_strength_returns_first() -> None:
    candidates = [_detail("10", "Lisinopril 10 mg Tablet")]
    chosen = select_medication("Lisinopril", candidates)
    assert chosen is not None
    assert chosen.fdb_code == "10"


def test_select_medication_empty() -> None:
    assert select_medication("Lisinopril 20 mg", []) is None


@patch("hyperscribe.scribe.recommendations._medication_match.CanvasScience.medication_details")
def test_resolve_searches_medication_name_first(mock_details: MagicMock) -> None:
    mock_details.return_value = [
        _detail("10", "Lisinopril 10 mg Tablet"),
        _detail("20", "Lisinopril 20 mg Tablet"),
    ]
    result = resolve_medication_detail("Lisinopril 20 mg", "lisinopril, prinivil")
    assert result is not None
    assert result.fdb_code == "20"
    # the full name is searched first and already yields the match, so no
    # keyword search is needed
    mock_details.assert_called_once_with(["Lisinopril 20 mg"])


@patch("hyperscribe.scribe.recommendations._medication_match.CanvasScience.medication_details")
def test_resolve_falls_back_to_keywords_when_name_search_empty(mock_details: MagicMock) -> None:
    mock_details.side_effect = [
        [],  # medication_name search returns nothing
        [
            _detail("10", "Lisinopril 10 mg Tablet"),
            _detail("20", "Lisinopril 20 mg Tablet"),
        ],
    ]
    result = resolve_medication_detail("Lisinopril 20 mg", "lisinopril")
    assert result is not None
    assert result.fdb_code == "20"
    assert mock_details.call_count == 2


@patch("hyperscribe.scribe.recommendations._medication_match.CanvasScience.medication_details")
def test_resolve_caches_per_expression(mock_details: MagicMock) -> None:
    mock_details.return_value = [_detail("10", "Lisinopril 10 mg Tablet")]
    cache: dict[str, list[MedicationDetail]] = {}
    resolve_medication_detail("Lisinopril 10 mg", "lisinopril", cache)
    resolve_medication_detail("Lisinopril 10 mg", "lisinopril", cache)
    # second call is served entirely from cache
    mock_details.assert_called_once_with(["Lisinopril 10 mg"])


@patch("hyperscribe.scribe.recommendations._medication_match.CanvasScience.medication_details")
def test_resolve_no_results(mock_details: MagicMock) -> None:
    mock_details.return_value = []
    assert resolve_medication_detail("Nonexistent 5 mg", "nonexistent") is None


def test_sanitize_sig_keeps_real_directions() -> None:
    assert sanitize_sig("Take 1 tablet by mouth daily") == "Take 1 tablet by mouth daily"
    # surrounding whitespace is trimmed but content preserved
    assert sanitize_sig("  Take 1 tablet daily  ") == "Take 1 tablet daily"


def test_sanitize_sig_blanks_angle_bracket_placeholder() -> None:
    assert sanitize_sig("<UNKNOWN>") == ""
    assert sanitize_sig("<unknown>") == ""
    assert sanitize_sig("<none stated>") == ""


def test_sanitize_sig_blanks_known_tokens() -> None:
    for token in ["unknown", "Unknown", "N/A", "n/a", "none", "NULL", "-", "TBD", "?", ""]:
        assert sanitize_sig(token) == "", token


def test_sanitize_sig_none() -> None:
    assert sanitize_sig(None) == ""
