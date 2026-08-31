from __future__ import annotations

import json
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from canvas_sdk.clients.llms.structures import LlmResponse, LlmTokens

from hyperscribe.scribe.backend.models import ClinicalNote, NoteSection
from hyperscribe.scribe.recommendations.allergy import (
    AllergyRecommender,
    _build_user_prompt,
    _resolve_allergy,
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
        NoteSection(key="allergies", title="Allergies", text="Penicillin (rash). Sulfa drugs (hives)."),
    ]
    result = _build_user_prompt(sections)
    assert "## Allergies" in result
    assert "Penicillin" in result


@patch("hyperscribe.scribe.recommendations.allergy.CanvasScience.search_allergy")
def test_resolve_allergy_found(mock_search: MagicMock) -> None:
    from hyperscribe.structures.allergy_detail import AllergyDetail

    mock_search.return_value = [
        AllergyDetail(
            concept_id_value=100,
            concept_id_description="Penicillin",
            concept_type="Allergen Group",
            concept_id_type=1,
        ),
    ]
    result = _resolve_allergy("penicillin, penicillin allergy")
    assert result is not None
    assert result["concept_id"] == 100
    assert result["concept_id_type"] == 1
    mock_search.assert_called_once()


@patch("hyperscribe.scribe.recommendations.allergy.CanvasScience.search_allergy")
def test_resolve_allergy_not_found(mock_search: MagicMock) -> None:
    mock_search.return_value = []
    result = _resolve_allergy("xyznonexistent")
    assert result is None


@patch("hyperscribe.scribe.recommendations.allergy._resolve_allergy")
def test_recommend_success(mock_resolve: MagicMock) -> None:
    mock_resolve.return_value = {"concept_id": 100, "concept_id_type": 1}

    note = _make_note(
        [
            NoteSection(key="allergies", title="Allergies", text="Penicillin (rash). Sulfa drugs (hives)."),
        ]
    )
    client = _make_client(
        {
            "allergies": [
                {
                    "allergen": "Penicillin",
                    "reaction": "rash",
                    "severity": "moderate",
                    "keywords": "penicillin",
                },
            ]
        }
    )

    recommender = AllergyRecommender()
    proposals = recommender.recommend(note, client)

    assert len(proposals) == 1
    assert proposals[0].command_type == "allergy"
    assert proposals[0].display == "Penicillin"
    assert proposals[0].data["reaction"] == "rash"
    assert proposals[0].data["severity"] == "moderate"
    assert proposals[0].data["concept_id"] == 100
    assert proposals[0].section_key == "_recommended"


@patch("hyperscribe.scribe.recommendations.allergy._resolve_allergy")
def test_recommend_no_concept_match(mock_resolve: MagicMock) -> None:
    mock_resolve.return_value = None

    note = _make_note(
        [
            NoteSection(key="allergies", title="Allergies", text="Pollen (sneezing)"),
        ]
    )
    client = _make_client(
        {
            "allergies": [
                {"allergen": "Pollen", "reaction": "sneezing", "severity": "mild", "keywords": "pollen"},
            ]
        }
    )

    recommender = AllergyRecommender()
    proposals = recommender.recommend(note, client)

    assert len(proposals) == 1
    assert proposals[0].data["concept_id"] is None
    assert proposals[0].data["concept_id_type"] is None


def test_recommend_empty_note() -> None:
    note = _make_note(
        [
            NoteSection(key="vitals", title="Vitals", text="BP 120/80"),
        ]
    )
    client = _make_client()

    recommender = AllergyRecommender()
    proposals = recommender.recommend(note, client)

    assert proposals == []
    client.request.assert_not_called()


def test_recommend_llm_error() -> None:
    note = _make_note(
        [
            NoteSection(key="allergies", title="Allergies", text="Penicillin"),
        ]
    )
    client = MagicMock()
    client.request.return_value = LlmResponse(
        code=HTTPStatus.INTERNAL_SERVER_ERROR,
        response="Server error",
        tokens=LlmTokens(prompt=0, generated=0),
    )

    recommender = AllergyRecommender()
    proposals = recommender.recommend(note, client)

    assert proposals == []


def test_recommend_llm_exception() -> None:
    note = _make_note(
        [
            NoteSection(key="allergies", title="Allergies", text="Penicillin"),
        ]
    )
    client = MagicMock()
    client.request.side_effect = Exception("Network error")

    recommender = AllergyRecommender()
    proposals = recommender.recommend(note, client)

    assert proposals == []


def test_recommend_malformed_response() -> None:
    note = _make_note(
        [
            NoteSection(key="allergies", title="Allergies", text="Penicillin"),
        ]
    )
    client = MagicMock()
    client.request.return_value = LlmResponse(
        code=HTTPStatus.OK,
        response="not valid json",
        tokens=LlmTokens(prompt=100, generated=50),
    )

    recommender = AllergyRecommender()
    proposals = recommender.recommend(note, client)

    assert proposals == []


@patch("hyperscribe.scribe.recommendations.allergy._resolve_allergy")
def test_recommend_invalid_severity_normalized_to_none(mock_resolve: MagicMock) -> None:
    mock_resolve.return_value = {"concept_id": 100, "concept_id_type": 1}

    note = _make_note(
        [
            NoteSection(key="allergies", title="Allergies", text="Penicillin (bad reaction)"),
        ]
    )
    client = _make_client(
        {
            "allergies": [
                {"allergen": "Penicillin", "reaction": "bad reaction", "severity": "extreme", "keywords": "penicillin"},
            ]
        }
    )

    recommender = AllergyRecommender()
    proposals = recommender.recommend(note, client)

    assert len(proposals) == 1
    assert proposals[0].data["severity"] is None


@patch("hyperscribe.scribe.recommendations.allergy._resolve_allergy")
def test_recommend_multiple_allergies(mock_resolve: MagicMock) -> None:
    mock_resolve.side_effect = [
        {"concept_id": 100, "concept_id_type": 1},
        {"concept_id": 200, "concept_id_type": 2},
    ]

    note = _make_note(
        [
            NoteSection(key="allergies", title="Allergies", text="Penicillin (rash). Sulfa drugs (hives)."),
        ]
    )
    client = _make_client(
        {
            "allergies": [
                {"allergen": "Penicillin", "reaction": "rash", "severity": "moderate", "keywords": "penicillin"},
                {"allergen": "Sulfa drugs", "reaction": "hives", "severity": "mild", "keywords": "sulfa"},
            ]
        }
    )

    recommender = AllergyRecommender()
    proposals = recommender.recommend(note, client)

    assert len(proposals) == 2
    assert proposals[0].display == "Penicillin"
    assert proposals[1].display == "Sulfa drugs"
