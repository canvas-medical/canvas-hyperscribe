from __future__ import annotations

import json
from http import HTTPStatus
from unittest.mock import MagicMock

from canvas_sdk.clients.llms.structures import LlmResponse, LlmTokens

from hyperscribe.scribe.backend.models import ClinicalNote, NoteSection
from hyperscribe.scribe.recommendations.refer import (
    ReferRecommender,
    _build_user_prompt,
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
        NoteSection(key="assessment_and_plan", title="Assessment & Plan", text="Refer to ENT."),
        NoteSection(key="history_of_present_illness", title="HPI", text="Chronic sinusitis."),
    ]
    result = _build_user_prompt(sections)
    assert "## Assessment & Plan" in result
    assert "ENT" in result
    assert "## HPI" in result


def test_recommend_is_generic_with_placeholder_provider() -> None:
    note = _make_note([NoteSection(key="assessment_and_plan", title="A&P", text="Refer to ENT.")])
    client = _make_client(
        {
            "referrals": [
                {
                    "specialty": "ENT",
                    "indication": "Chronic sinusitis",
                    "clinicalQuestion": "Specialized intervention",
                    "reason": "Further evaluation needed",
                },
            ]
        }
    )

    proposals = ReferRecommender().recommend(note, client)

    assert len(proposals) == 1
    p = proposals[0]
    assert p.command_type == "refer"
    # generic: display is the specialty; recipient is a placeholder, not a real provider
    assert p.display == "ENT"
    assert p.data["refer_to_display"] == "ENT"
    sp = p.data["service_provider"]
    # Canvas core rejects a blank first_name, so placeholder names are non-empty
    assert sp["first_name"] == "TBD"
    assert sp["last_name"] == "TBD"
    assert sp["specialty"] == "ENT"
    assert sp["practice_name"] == "ENT"
    assert p.data["indication"] == "Chronic sinusitis"
    assert p.data["clinical_question"] == "Specialized intervention"
    # priority is left blank for the provider to set
    assert "priority" not in p.data
    assert p.data["notes_to_specialist"] == "Further evaluation needed"


def test_recommend_defaults_clinical_question_and_notes() -> None:
    note = _make_note([NoteSection(key="plan", title="Plan", text="Refer to cardiology.")])
    client = _make_client({"referrals": [{"specialty": "Cardiology"}]})

    proposals = ReferRecommender().recommend(note, client)

    assert len(proposals) == 1
    data = proposals[0].data
    assert data["indication"] is None
    # defaults fill the sign-required fields
    assert data["clinical_question"] == "Assistance with Ongoing Management"
    assert data["notes_to_specialist"] == "Referral to Cardiology"
    assert data["service_provider"]["last_name"] == "TBD"


def test_recommend_notes_fall_back_to_indication() -> None:
    note = _make_note([NoteSection(key="plan", title="Plan", text="Refer to ortho.")])
    client = _make_client(
        {"referrals": [{"specialty": "Orthopedics", "indication": "Rotator cuff tear"}]}
    )

    proposals = ReferRecommender().recommend(note, client)

    assert proposals[0].data["notes_to_specialist"] == "Rotator cuff tear"


def test_recommend_multiple_referrals_all_generic() -> None:
    note = _make_note([NoteSection(key="plan", title="Plan", text="Refer to ENT and Dermatology.")])
    client = _make_client(
        {
            "referrals": [
                {"specialty": "ENT", "indication": "Sinusitis"},
                {"specialty": "Dermatology", "indication": "Rash"},
            ]
        }
    )

    proposals = ReferRecommender().recommend(note, client)

    assert len(proposals) == 2
    assert [p.display for p in proposals] == ["ENT", "Dermatology"]
    assert all(p.data["service_provider"]["last_name"] == "TBD" for p in proposals)
    assert all("priority" not in p.data for p in proposals)


def test_recommend_skips_blank_specialty() -> None:
    note = _make_note([NoteSection(key="plan", title="Plan", text="Refer out.")])
    client = _make_client({"referrals": [{"specialty": "  "}]})

    assert ReferRecommender().recommend(note, client) == []


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


def test_recommend_no_referrals_found() -> None:
    note = _make_note([NoteSection(key="assessment_and_plan", title="A&P", text="Continue meds.")])
    client = _make_client({"referrals": []})

    assert ReferRecommender().recommend(note, client) == []
