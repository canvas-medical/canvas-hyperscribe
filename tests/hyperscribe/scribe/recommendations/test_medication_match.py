from __future__ import annotations

from unittest.mock import MagicMock, patch

import re

from hyperscribe.scribe.recommendations._medication_match import (
    ascii_fold_sig,
    extract_strengths,
    resolve_medication_detail,
    sanitize_sig,
    select_medication,
)
from hyperscribe.structures.medication_detail import MedicationDetail

# Mirrors _rx_validation._RE_INVALID_CHARACTERS — anything outside printable ASCII.
_NON_ASCII = re.compile(r"[^ -~]")


def _detail(fdb_code: str, description: str) -> MedicationDetail:
    return MedicationDetail(fdb_code=fdb_code, description=description, quantities=[])


def test_extract_strengths_normalizes_units_and_spacing() -> None:
    # mass strengths canonicalize to micrograms ("20 mg" -> "20000mcg")
    assert extract_strengths("Lisinopril 20 mg tablet") == {"20000mcg"}
    assert extract_strengths("Lisinopril 20mg") == {"20000mcg"}
    assert extract_strengths("Lisinopril 20 MG") == {"20000mcg"}
    assert extract_strengths("Levothyroxine 0.5 mcg") == {"0.5mcg"}


def test_extract_strengths_spelled_out_units() -> None:
    # the extraction prompt preserves the note's wording, so spelled-out units
    # must parse to the same token as their abbreviation (KOALA-5930)
    assert extract_strengths("levothyroxine 75 micrograms") == {"75mcg"}
    assert extract_strengths("levothyroxine 75 microgram") == {"75mcg"}
    assert extract_strengths("amoxicillin 500 milligrams") == {"500000mcg"}
    assert extract_strengths("acetaminophen 1 gram") == {"1000000mcg"}
    assert extract_strengths("levothyroxine 75 micrograms") == extract_strengths("levothyroxine 75 mcg")


def test_extract_strengths_cross_unit_mass_equivalence() -> None:
    # mcg <-> mg <-> g all express in micrograms, so equivalent strengths match
    assert extract_strengths("levothyroxine 0.075 mg") == {"75mcg"}
    assert extract_strengths("levothyroxine 0.075 mg") == extract_strengths("levothyroxine 75 mcg")
    # 1 g == 1000 mg
    assert extract_strengths("acetaminophen 1 g") == extract_strengths("acetaminophen 1000 mg")


def test_extract_strengths_no_strength() -> None:
    assert extract_strengths("Lisinopril") == set()
    assert extract_strengths("") == set()


def test_extract_strengths_combination_product() -> None:
    # combination strengths split into one token per component, sharing the unit
    assert extract_strengths("Lisinopril-HCTZ 20-12.5 mg tablet") == {"20000mcg", "12500mcg"}
    assert extract_strengths("Symbicort 160/4.5 mcg") == {"160mcg", "4.5mcg"}
    # and FDB's split rendering of the same product yields the same tokens
    assert extract_strengths("Symbicort 160 mcg-4.5 mcg/actuation HFA") == {"160mcg", "4.5mcg"}


def test_extract_strengths_comma_thousands_separator() -> None:
    assert extract_strengths("metformin 1,000 mg tablet") == {"1000000mcg"}
    assert extract_strengths("metformin 1000 mg") == {"1000000mcg"}
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
    assert extract_strengths("Lisinopril 120 mg") == {"120000mcg"}
    assert "20000mcg" not in extract_strengths("Lisinopril 120 mg")


def test_extract_strengths_units_dose_vs_concentration() -> None:
    # A bare per-dose amount ("30 units") must NOT match a concentration/rate
    # product whose description carries the same number with a denominator —
    # the insulin-glargine -> Omnipod misresolution (KOALA-5930).
    assert extract_strengths("insulin glargine 30 units") == {"30unit"}
    assert extract_strengths("Omnipod Go Pods 30 units/day subcutaneous cartridge") == {"30unit/day"}
    assert extract_strengths("insulin glargine 100 units/mL") == {"100unit/ml"}
    assert not {"30unit"}.issubset(extract_strengths("Omnipod Go Pods 30 units/day subcutaneous cartridge"))
    assert not {"30unit"}.issubset(extract_strengths("insulin glargine 100 units/mL"))
    # but a bare unit count (vitamin D 2000 unit tablet) still matches a bare count
    assert extract_strengths("vitamin D 2000 units").issubset(
        extract_strengths("Vitamin D3 50 mcg (2,000 unit) tablet")
    )


def test_select_medication_prefers_stated_strength() -> None:
    candidates = [
        _detail("10", "Lisinopril 10 mg Tablet"),
        _detail("20", "Lisinopril 20 mg Tablet"),
    ]
    chosen = select_medication("Lisinopril 20 mg", candidates)
    assert chosen is not None
    assert chosen.fdb_code == "20"


def test_select_medication_returns_none_on_unmatched_strength() -> None:
    candidates = [
        _detail("10", "Lisinopril 10 mg Tablet"),
        _detail("40", "Lisinopril 40 mg Tablet"),
    ]
    # a strength WAS stated but no candidate carries 5 mg -> None (fail-safe),
    # rather than a wrong-strength candidate
    assert select_medication("Lisinopril 5 mg", candidates) is None


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


@patch("hyperscribe.scribe.recommendations._medication_match.CanvasScience.medication_details")
def test_resolve_spelled_out_strength(mock_details: MagicMock) -> None:
    # "75 micrograms" (spelled out) resolves to the 75 mcg product, not the
    # first candidate (the levothyroxine 75 mcg -> 50 mcg miss, KOALA-5930)
    mock_details.return_value = [
        _detail("50", "levothyroxine 50 mcg tablet"),
        _detail("75", "levothyroxine 75 mcg tablet"),
        _detail("100", "levothyroxine 100 mcg tablet"),
    ]
    result = resolve_medication_detail("levothyroxine 75 micrograms", "levothyroxine, synthroid")
    assert result is not None
    assert result.fdb_code == "75"


@patch("hyperscribe.scribe.recommendations._medication_match.CanvasScience.medication_details")
def test_resolve_cross_unit_strength(mock_details: MagicMock) -> None:
    # "0.075 mg" resolves to the FDB product stored as "75 mcg" (mcg <-> mg)
    mock_details.return_value = [
        _detail("50", "levothyroxine 50 mcg tablet"),
        _detail("75", "levothyroxine 75 mcg tablet"),
    ]
    result = resolve_medication_detail("levothyroxine 0.075 mg", "levothyroxine")
    assert result is not None
    assert result.fdb_code == "75"


@patch("hyperscribe.scribe.recommendations._medication_match.CanvasScience.medication_details")
def test_resolve_returns_none_on_unmatched_strength(mock_details: MagicMock) -> None:
    # stated 75 mcg but FDB top results lack it -> None (leave unresolved),
    # never the wrong-strength 50 mcg candidate
    mock_details.return_value = [
        _detail("50", "levothyroxine 50 mcg tablet"),
        _detail("100", "levothyroxine 100 mcg tablet"),
    ]
    assert resolve_medication_detail("levothyroxine 75 mcg", "levothyroxine") is None


@patch("hyperscribe.scribe.recommendations._medication_match.CanvasScience.medication_details")
def test_resolve_insulin_units_never_matches_unrelated_product(mock_details: MagicMock) -> None:
    # the stated dose "30 units" must not resolve to the "30 units/day" device;
    # glargine is 100 units/mL, so nothing matches -> None (KOALA-5930 comment 2)
    mock_details.return_value = [
        _detail("615066", "Omnipod Go Pods 30 units/day subcutaneous cartridge"),
        _detail("glargine", "insulin glargine 100 units/mL"),
    ]
    assert resolve_medication_detail("insulin glargine 30 units", "insulin glargine, lantus") is None


@patch("hyperscribe.scribe.recommendations._medication_match.CanvasScience.medication_details")
def test_resolve_spot_check_exact_strengths(mock_details: MagicMock) -> None:
    # no systematic exact-strength miss across nearby levothyroxine strengths
    levo = [
        _detail("88", "levothyroxine 88 mcg tablet"),
        _detail("112", "levothyroxine 112 mcg tablet"),
        _detail("125", "levothyroxine 125 mcg tablet"),
    ]
    for code, mcg in [("88", "88"), ("112", "112"), ("125", "125")]:
        mock_details.return_value = list(levo)
        result = resolve_medication_detail(f"levothyroxine {mcg} mcg", "levothyroxine")
        assert result is not None and result.fdb_code == code

    statins = [
        _detail("10", "atorvastatin 10 mg tablet"),
        _detail("20", "atorvastatin 20 mg tablet"),
        _detail("40", "atorvastatin 40 mg tablet"),
    ]
    for code, mg in [("10", "10"), ("20", "20"), ("40", "40")]:
        mock_details.return_value = list(statins)
        result = resolve_medication_detail(f"atorvastatin {mg} mg", "atorvastatin, lipitor")
        assert result is not None and result.fdb_code == code


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


def test_sanitize_sig_folds_en_dash() -> None:
    # The regression that prompted this: azithromycin "days 2–5" (en-dash) fails
    # Surescripts sig validation; it must fold to an ASCII hyphen.
    result = sanitize_sig("take 2 tablets on day 1, then 1 tablet daily on days 2–5")
    assert result == "take 2 tablets on day 1, then 1 tablet daily on days 2-5"
    assert not _NON_ASCII.search(result)


def test_sanitize_sig_folds_typographic_characters() -> None:
    assert ascii_fold_sig("don’t exceed 3…") == "don't exceed 3..."
    assert ascii_fold_sig("“twice” daily") == '"twice" daily'
    assert ascii_fold_sig("1 tablet daily") == "1 tablet daily"


def test_sanitize_sig_preserves_micrograms() -> None:
    # Stripping the micro sign would turn "µg" into "g" — a 1000x dosing error.
    assert sanitize_sig("take 50 µg by mouth daily") == "take 50 mcg by mouth daily"
    assert sanitize_sig("take 50 μg by mouth daily") == "take 50 mcg by mouth daily"


def test_sanitize_sig_drops_residual_non_ascii() -> None:
    # unicodedata isn't allowed in the sandbox, so accents aren't folded to their
    # base letter — residual non-ASCII is simply dropped. The guarantee is only
    # that the result is pure printable ASCII (what Surescripts requires).
    folded = sanitize_sig("apply to café area 5°")
    assert not _NON_ASCII.search(folded)
    assert "area" in folded
