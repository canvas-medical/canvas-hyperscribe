from __future__ import annotations

import json
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from canvas_sdk.clients.llms.structures import LlmResponse, LlmTokens

from hyperscribe.scribe.backend.models import ClinicalNote, NoteSection
from hyperscribe.scribe.recommendations.medication_statement import (
    MedicationRecommender,
    _build_user_prompt,
    _resolve_medication,
)


def _make_note(sections: list[NoteSection] | None = None) -> ClinicalNote:
    return ClinicalNote(title="Test Note", sections=sections or [])


def _make_client(response_data: dict | None = None, code: HTTPStatus = HTTPStatus.OK) -> MagicMock:
    client = MagicMock()
    if response_data is not None:
        client.request.return_value = LlmResponse(
            code=code,
            response=json.dumps(response_data),
            tokens=LlmTokens(prompt=100, generated=50),
        )
    return client


def test_build_user_prompt() -> None:
    sections = [
        NoteSection(key="current_medications", title="Current Medications", text="- Lisinopril 10mg daily"),
        NoteSection(key="assessment_and_plan", title="Assessment & Plan", text="Start metformin."),
    ]
    result = _build_user_prompt(sections)
    assert "## Current Medications" in result
    assert "Lisinopril 10mg daily" in result
    assert "## Assessment & Plan" in result


@patch("hyperscribe.scribe.recommendations._medication_match.CanvasScience.medication_details")
def test_resolve_medication_found(mock_details: MagicMock) -> None:
    from hyperscribe.structures.medication_detail import MedicationDetail

    mock_details.return_value = [
        MedicationDetail(fdb_code="12345", description="Lisinopril 10mg Tablet", quantities=[]),
    ]
    result = _resolve_medication("Lisinopril 10mg", "lisinopril, lisinopril 10mg")
    assert result is not None
    assert result.fdb_code == "12345"
    assert result.description == "Lisinopril 10mg Tablet"
    # the full medication name is searched first so FDB returns the stated strength
    mock_details.assert_called_once_with(["Lisinopril 10mg"])


@patch("hyperscribe.scribe.recommendations._medication_match.CanvasScience.medication_details")
def test_resolve_medication_matches_stated_strength(mock_details: MagicMock) -> None:
    """Regression: a 20 mg statement must not resolve to the 10 mg group."""
    from hyperscribe.structures.medication_detail import MedicationDetail

    # FDB returns the 10 mg group first, then the 20 mg group.
    mock_details.return_value = [
        MedicationDetail(fdb_code="10", description="Lisinopril 10 mg Tablet", quantities=[]),
        MedicationDetail(fdb_code="20", description="Lisinopril 20 mg Tablet", quantities=[]),
    ]
    result = _resolve_medication("Lisinopril 20 mg", "lisinopril")
    assert result is not None
    assert result.fdb_code == "20"
    assert result.description == "Lisinopril 20 mg Tablet"


@patch("hyperscribe.scribe.recommendations._medication_match.CanvasScience.medication_details")
def test_resolve_medication_returns_none_when_no_strength_match(mock_details: MagicMock) -> None:
    from hyperscribe.structures.medication_detail import MedicationDetail

    mock_details.return_value = [
        MedicationDetail(fdb_code="10", description="Lisinopril 10 mg Tablet", quantities=[]),
        MedicationDetail(fdb_code="40", description="Lisinopril 40 mg Tablet", quantities=[]),
    ]
    # stated strength (5 mg) is not in the candidate set -> None (fail-safe),
    # so the proposal keeps the medication text without a wrong-strength FDB code
    assert _resolve_medication("Lisinopril 5 mg", "lisinopril") is None


@patch("hyperscribe.scribe.recommendations._medication_match.CanvasScience.medication_details")
def test_resolve_medication_not_found(mock_details: MagicMock) -> None:
    mock_details.return_value = []
    result = _resolve_medication("xyznonexistent 5mg", "xyznonexistent")
    assert result is None


@patch("hyperscribe.scribe.recommendations.medication_statement._resolve_medication")
def test_recommend_success(mock_resolve: MagicMock) -> None:
    from hyperscribe.structures.medication_detail import MedicationDetail

    mock_resolve.return_value = MedicationDetail(fdb_code="12345", description="Lisinopril 10mg Tablet", quantities=[])

    note = _make_note(
        [
            NoteSection(key="current_medications", title="Current Medications", text="- Lisinopril 10mg daily"),
        ]
    )
    client = _make_client(
        {
            "medications": [
                {"medicationName": "Lisinopril 10mg", "sig": "Take 1 tablet daily", "keywords": "lisinopril"},
            ]
        }
    )

    recommender = MedicationRecommender()
    proposals = recommender.recommend(note, client)

    assert len(proposals) == 1
    assert proposals[0].command_type == "medication_statement"
    assert proposals[0].display == "Lisinopril 10mg Tablet"
    assert proposals[0].data["medication_text"] == "Lisinopril 10mg Tablet"
    assert proposals[0].data["sig"] == "Take 1 tablet daily"
    assert proposals[0].data["fdb_code"]["system"] == "http://www.fdbhealth.com/"
    assert proposals[0].data["fdb_code"]["code"] == "12345"
    assert proposals[0].data["fdb_code"]["display"] == "Lisinopril 10mg Tablet"
    assert proposals[0].section_key == "_recommended"

    client.reset_prompts.assert_called_once()
    client.set_schema.assert_called_once()


@patch("hyperscribe.scribe.recommendations.medication_statement._resolve_medication")
def test_recommend_no_fdb_match(mock_resolve: MagicMock) -> None:
    mock_resolve.return_value = None

    note = _make_note(
        [
            NoteSection(key="current_medications", title="Current Medications", text="- SomeDrug 5mg daily"),
        ]
    )
    client = _make_client(
        {
            "medications": [
                {"medicationName": "SomeDrug 5mg", "sig": "Take daily", "keywords": "somedrug"},
            ]
        }
    )

    recommender = MedicationRecommender()
    proposals = recommender.recommend(note, client)

    assert len(proposals) == 1
    assert proposals[0].data["fdb_code"] is None
    assert proposals[0].data["medication_text"] == "SomeDrug 5mg"


@patch("hyperscribe.scribe.recommendations.medication_statement._resolve_medication")
def test_recommend_blanks_placeholder_sig(mock_resolve: MagicMock) -> None:
    """A medication with no stated directions surfaces a blank sig, not "<UNKNOWN>"."""
    mock_resolve.return_value = None

    note = _make_note(
        [
            NoteSection(key="current_medications", title="Current Medications", text="- Lisinopril 20mg"),
        ]
    )
    client = _make_client(
        {
            "medications": [
                {"medicationName": "Lisinopril 20mg", "sig": "<UNKNOWN>", "keywords": "lisinopril"},
            ]
        }
    )

    recommender = MedicationRecommender()
    proposals = recommender.recommend(note, client)

    assert len(proposals) == 1
    assert proposals[0].data["sig"] == ""


def test_recommend_empty_note() -> None:
    note = _make_note(
        [
            NoteSection(key="social_history", title="Social History", text="Non-smoker"),
        ]
    )
    client = _make_client()

    recommender = MedicationRecommender()
    proposals = recommender.recommend(note, client)

    assert proposals == []
    client.request.assert_not_called()


def test_recommend_llm_error() -> None:
    note = _make_note(
        [
            NoteSection(key="current_medications", title="Current Medications", text="- Lisinopril 10mg"),
        ]
    )
    client = _make_client(code=HTTPStatus.INTERNAL_SERVER_ERROR, response_data={"error": "fail"})
    client.request.return_value = LlmResponse(
        code=HTTPStatus.INTERNAL_SERVER_ERROR,
        response="Server error",
        tokens=LlmTokens(prompt=0, generated=0),
    )

    recommender = MedicationRecommender()
    proposals = recommender.recommend(note, client)

    assert proposals == []


def test_recommend_llm_exception() -> None:
    note = _make_note(
        [
            NoteSection(key="current_medications", title="Current Medications", text="- Lisinopril 10mg"),
        ]
    )
    client = MagicMock()
    client.request.side_effect = Exception("Network error")

    recommender = MedicationRecommender()
    proposals = recommender.recommend(note, client)

    assert proposals == []


def test_recommend_malformed_response() -> None:
    note = _make_note(
        [
            NoteSection(key="current_medications", title="Current Medications", text="- Lisinopril 10mg"),
        ]
    )
    client = MagicMock()
    client.request.return_value = LlmResponse(
        code=HTTPStatus.OK,
        response="not valid json",
        tokens=LlmTokens(prompt=100, generated=50),
    )

    recommender = MedicationRecommender()
    proposals = recommender.recommend(note, client)

    assert proposals == []


@patch("hyperscribe.scribe.recommendations.medication_statement._resolve_medication")
def test_recommend_multiple_medications(mock_resolve: MagicMock) -> None:
    from hyperscribe.structures.medication_detail import MedicationDetail

    mock_resolve.side_effect = [
        MedicationDetail(fdb_code="111", description="Lisinopril 10mg", quantities=[]),
        MedicationDetail(fdb_code="222", description="Metformin 500mg", quantities=[]),
    ]

    note = _make_note(
        [
            NoteSection(
                key="current_medications",
                title="Current Medications",
                text="- Lisinopril 10mg daily\n- Metformin 500mg BID",
            ),
        ]
    )
    client = _make_client(
        {
            "medications": [
                {"medicationName": "Lisinopril 10mg", "sig": "Take daily", "keywords": "lisinopril"},
                {"medicationName": "Metformin 500mg", "sig": "Take twice daily", "keywords": "metformin"},
            ]
        }
    )

    recommender = MedicationRecommender()
    proposals = recommender.recommend(note, client)

    assert len(proposals) == 2
    assert proposals[0].display == "Lisinopril 10mg"
    assert proposals[0].data["fdb_code"]["code"] == "111"
    assert proposals[1].display == "Metformin 500mg"
    assert proposals[1].data["fdb_code"]["code"] == "222"
