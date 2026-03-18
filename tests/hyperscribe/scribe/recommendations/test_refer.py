from __future__ import annotations

import json
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from canvas_sdk.clients.llms.structures import LlmResponse, LlmTokens

from hyperscribe.scribe.backend.models import ClinicalNote, NoteSection
from hyperscribe.scribe.recommendations.refer import (
    ReferRecommender,
    _build_user_prompt,
)

_MATCHED_RESULT = {
    "name": "Jane Smith (ENT Clinic), Otolaryngology",
    "description": "Phone: 555-1234",
    "data": {
        "first_name": "Jane",
        "last_name": "Smith",
        "specialty": "Otolaryngology",
        "practice_name": "ENT Clinic",
        "business_fax": "",
        "business_phone": "555-1234",
        "business_address": "123 Main St",
    },
}

_DERM_RESULT = {
    "name": "Bob Brown (Skin Clinic), Dermatology",
    "description": "",
    "data": {
        "first_name": "Bob",
        "last_name": "Brown",
        "specialty": "Dermatology",
        "practice_name": "Skin Clinic",
        "business_fax": "",
        "business_phone": "",
        "business_address": "",
    },
}


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
        NoteSection(key="assessment_and_plan", title="Assessment & Plan", text="Refer to ENT."),
        NoteSection(key="history_of_present_illness", title="HPI", text="Chronic sinusitis."),
    ]
    result = _build_user_prompt(sections)
    assert "## Assessment & Plan" in result
    assert "ENT" in result
    assert "## HPI" in result


@patch("hyperscribe.scribe.recommendations.refer.search_refer_providers")
def test_recommend_with_matching_provider(mock_search: MagicMock) -> None:
    mock_search.return_value = [_MATCHED_RESULT]

    note = _make_note([NoteSection(key="assessment_and_plan", title="A&P", text="Refer to ENT.")])
    client = _make_client(
        {
            "referrals": [
                {
                    "specialty": "ENT",
                    "clinicalQuestion": "Specialized intervention",
                    "priority": "Routine",
                    "reason": "Further evaluation needed",
                },
            ]
        }
    )

    proposals = ReferRecommender().recommend(note, client)

    assert len(proposals) == 1
    assert proposals[0].command_type == "refer"
    assert proposals[0].data["service_provider"]["first_name"] == "Jane"
    assert proposals[0].data["refer_to_display"] == "Jane Smith (ENT Clinic), Otolaryngology"
    assert proposals[0].data["clinical_question"] == "Specialized intervention"
    assert proposals[0].data["notes_to_specialist"] == "Further evaluation needed"
    mock_search.assert_called_once_with("ENT", None)


@patch("hyperscribe.scribe.recommendations.refer.search_refer_providers")
def test_recommend_incomplete_when_no_provider_found(mock_search: MagicMock) -> None:
    mock_search.return_value = []

    note = _make_note([NoteSection(key="assessment_and_plan", title="A&P", text="Refer to ENT.")])
    client = _make_client({"referrals": [{"specialty": "ENT", "priority": "Routine", "reason": "Evaluation needed"}]})

    proposals = ReferRecommender().recommend(note, client)

    assert len(proposals) == 1
    assert proposals[0].command_type == "refer"
    assert proposals[0].display == "ENT"
    assert proposals[0].data.get("service_provider") is None
    assert proposals[0].data.get("refer_to_display") is None
    assert proposals[0].data["priority"] == "Routine"
    assert proposals[0].data["notes_to_specialist"] == "Evaluation needed"
    mock_search.assert_called_once_with("ENT", None)


@patch("hyperscribe.scribe.recommendations.refer.search_refer_providers")
def test_recommend_multiple_mixed_matches(mock_search: MagicMock) -> None:
    mock_search.side_effect = [
        [],  # ENT not found → incomplete
        [_DERM_RESULT],
    ]

    note = _make_note([NoteSection(key="plan", title="Plan", text="Refer to ENT and Dermatology.")])
    client = _make_client(
        {
            "referrals": [
                {"specialty": "ENT", "priority": "Routine"},
                {"specialty": "Dermatology", "priority": "Routine"},
            ]
        }
    )

    proposals = ReferRecommender().recommend(note, client)

    assert len(proposals) == 2
    assert proposals[0].data.get("service_provider") is None
    assert proposals[0].data.get("refer_to_display") is None
    assert proposals[1].data["service_provider"]["specialty"] == "Dermatology"


def test_recommend_empty_note() -> None:
    note = _make_note([NoteSection(key="social_history", title="Social History", text="Non-smoker")])
    client = _make_client()

    proposals = ReferRecommender().recommend(note, client)

    assert proposals == []
    client.request.assert_not_called()


def test_recommend_llm_error() -> None:
    note = _make_note([NoteSection(key="assessment_and_plan", title="A&P", text="Refer to cardiology.")])
    client = MagicMock()
    client.request.return_value = LlmResponse(
        code=HTTPStatus.INTERNAL_SERVER_ERROR,
        response="Server error",
        tokens=LlmTokens(prompt=0, generated=0),
    )

    assert ReferRecommender().recommend(note, client) == []


def test_recommend_llm_exception() -> None:
    note = _make_note([NoteSection(key="assessment_and_plan", title="A&P", text="Refer to cardiology.")])
    client = MagicMock()
    client.request.side_effect = Exception("Network error")

    assert ReferRecommender().recommend(note, client) == []


def test_recommend_malformed_response() -> None:
    note = _make_note([NoteSection(key="assessment_and_plan", title="A&P", text="Refer to cardiology.")])
    client = MagicMock()
    client.request.return_value = LlmResponse(
        code=HTTPStatus.OK,
        response="not valid json",
        tokens=LlmTokens(prompt=100, generated=50),
    )

    assert ReferRecommender().recommend(note, client) == []


@patch("hyperscribe.scribe.recommendations.refer.search_refer_providers")
def test_recommend_no_referrals_found(mock_search: MagicMock) -> None:
    note = _make_note([NoteSection(key="assessment_and_plan", title="A&P", text="Continue meds.")])
    client = _make_client({"referrals": []})

    assert ReferRecommender().recommend(note, client) == []
    mock_search.assert_not_called()
