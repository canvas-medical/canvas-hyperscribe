"""Tests for the grounded ICD-10 suggester (``suggest_diagnoses``).

The free-generation path (LLM emits codes, existence-checked only) is gone. The
suggester now returns ONLY codes the Canvas science service actually returns for
the condition text — so a code the ontology does not surface can never appear.
These tests assert exactly that anti-hallucination property.
"""

from __future__ import annotations

from unittest.mock import patch

from hyperscribe.scribe.recommendations.diagnosis_suggestion import suggest_diagnoses
from hyperscribe.structures.icd10_condition import Icd10Condition


def test_suggest_diagnoses_returns_only_science_codes() -> None:
    search_results = [
        Icd10Condition(code="G43909", label="Migraine, unspecified, not intractable"),
        Icd10Condition(code="G44209", label="Tension-type headache, unspecified"),
    ]
    with patch(
        "hyperscribe.scribe.recommendations.diagnosis_suggestion.CanvasScience.search_conditions",
        return_value=search_results,
    ):
        result = suggest_diagnoses(["Headache"])

    options = result["Headache"]
    returned_codes = {option["code"] for option in options}
    science_codes = {c.code for c in search_results}
    # Every surfaced code came from the science service — nothing invented.
    assert returned_codes <= science_codes
    assert returned_codes  # and we did surface the grounded options
    assert all("provenance" in option for option in options)


def test_suggest_diagnoses_no_science_match_is_empty() -> None:
    with patch(
        "hyperscribe.scribe.recommendations.diagnosis_suggestion.CanvasScience.search_conditions",
        return_value=[],
    ):
        result = suggest_diagnoses(["Some freetext with no ontology match"])
    # No fabricated codes — the provider falls back to manual search.
    assert result["Some freetext with no ontology match"] == []


def test_suggest_diagnoses_empty_and_blank_conditions() -> None:
    assert suggest_diagnoses([]) == {}
    with patch(
        "hyperscribe.scribe.recommendations.diagnosis_suggestion.CanvasScience.search_conditions",
        return_value=[],
    ):
        assert suggest_diagnoses(["   "]) == {}


def test_suggest_diagnoses_never_invents_off_list_code() -> None:
    # Even if the science service returns one narrow result, the output is a strict
    # subset of it — there is no path that adds a code the ontology didn't return.
    with patch(
        "hyperscribe.scribe.recommendations.diagnosis_suggestion.CanvasScience.search_conditions",
        return_value=[Icd10Condition(code="E039", label="Hypothyroidism, unspecified")],
    ):
        result = suggest_diagnoses(["Hypothyroidism"])
    assert [option["code"] for option in result["Hypothyroidism"]] == ["E039"]
