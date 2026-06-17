from __future__ import annotations

from unittest.mock import MagicMock, patch

from hyperscribe.scribe.recommendations._medication_match import (
    extract_strengths,
    resolve_medication_detail,
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
    assert extract_strengths("Lisinopril-HCTZ 20-12.5 mg tablet") == {"20-12.5mg"}


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
