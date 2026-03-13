from __future__ import annotations

import json
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from canvas_sdk.clients.llms.structures import LlmResponse, LlmTokens

from hyperscribe.scribe.backend.models import ClinicalNote, NoteSection
from hyperscribe.scribe.recommendations.prescription import (
    PrescriptionRecommender,
    _build_user_prompt,
    _resolve_prescription,
)
from hyperscribe.structures.medication_detail import MedicationDetail
from hyperscribe.structures.medication_detail_quantity import MedicationDetailQuantity


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
        NoteSection(key="assessment_and_plan", title="Assessment & Plan", text="Start sumatriptan 50mg."),
        NoteSection(key="history_of_present_illness", title="HPI", text="Patient has migraines."),
    ]
    result = _build_user_prompt(sections)
    assert "## Assessment & Plan" in result
    assert "sumatriptan" in result
    assert "## HPI" in result


@patch("hyperscribe.scribe.recommendations.prescription.CanvasScience.medication_details")
def test_resolve_prescription_found(mock_details: MagicMock) -> None:
    detail = MedicationDetail(
        fdb_code="99999",
        description="Sumatriptan 50mg Tablet",
        quantities=[
            MedicationDetailQuantity(
                quantity="9",
                representative_ndc="12345678901",
                clinical_quantity_description="Tablet",
                ncpdp_quantity_qualifier_code="C48542",
                ncpdp_quantity_qualifier_description="Tablet",
            ),
        ],
    )
    mock_details.return_value = [detail]
    result = _resolve_prescription("sumatriptan, sumatriptan 50mg")
    assert result is not None
    assert result.fdb_code == "99999"
    assert result.description == "Sumatriptan 50mg Tablet"
    assert len(result.quantities) == 1
    mock_details.assert_called_once_with(["sumatriptan"])


@patch("hyperscribe.scribe.recommendations.prescription.CanvasScience.medication_details")
def test_resolve_prescription_not_found(mock_details: MagicMock) -> None:
    mock_details.return_value = []
    result = _resolve_prescription("xyznonexistent")
    assert result is None


@patch("hyperscribe.scribe.recommendations.prescription._resolve_prescription")
def test_recommend_success(mock_resolve: MagicMock) -> None:
    detail = MedicationDetail(
        fdb_code="99999",
        description="Sumatriptan 50mg Tablet",
        quantities=[
            MedicationDetailQuantity(
                quantity="9",
                representative_ndc="12345678901",
                clinical_quantity_description="Tablet",
                ncpdp_quantity_qualifier_code="C48542",
                ncpdp_quantity_qualifier_description="Tablet",
            ),
        ],
    )
    mock_resolve.return_value = detail

    note = _make_note(
        [
            NoteSection(
                key="assessment_and_plan",
                title="Assessment & Plan",
                text="Start sumatriptan 50mg at onset.",
            ),
        ]
    )
    client = _make_client(
        {
            "prescriptions": [
                {
                    "medicationName": "Sumatriptan 50mg",
                    "sig": "Take 1 tablet at onset of migraine",
                    "daysSupply": 30,
                    "quantityToDispense": "9",
                    "refills": 2,
                    "keywords": "sumatriptan",
                },
            ]
        }
    )

    recommender = PrescriptionRecommender()
    proposals = recommender.recommend(note, client)

    assert len(proposals) == 1
    assert proposals[0].command_type == "prescribe"
    assert proposals[0].display == "Sumatriptan 50mg Tablet"
    assert proposals[0].data["fdb_code"] == "99999"
    assert proposals[0].data["medication_text"] == "Sumatriptan 50mg Tablet"
    assert proposals[0].data["sig"] == "Take 1 tablet at onset of migraine"
    assert proposals[0].data["days_supply"] == 30
    assert proposals[0].data["quantity_to_dispense"] == "9"
    assert proposals[0].data["refills"] == 2
    assert len(proposals[0].data["quantities"]) == 1
    assert proposals[0].data["quantities"][0]["representative_ndc"] == "12345678901"
    assert proposals[0].section_key == "_recommended"

    client.reset_prompts.assert_called_once()
    client.set_schema.assert_called_once()


@patch("hyperscribe.scribe.recommendations.prescription._resolve_prescription")
def test_recommend_no_fdb_match(mock_resolve: MagicMock) -> None:
    mock_resolve.return_value = None

    note = _make_note(
        [
            NoteSection(
                key="assessment_and_plan",
                title="Assessment & Plan",
                text="Start SomeDrug 5mg daily.",
            ),
        ]
    )
    client = _make_client(
        {
            "prescriptions": [
                {
                    "medicationName": "SomeDrug 5mg",
                    "sig": "Take daily",
                    "keywords": "somedrug",
                },
            ]
        }
    )

    recommender = PrescriptionRecommender()
    proposals = recommender.recommend(note, client)

    assert len(proposals) == 1
    assert proposals[0].data["fdb_code"] is None
    assert proposals[0].data["medication_text"] == "SomeDrug 5mg"
    assert proposals[0].data["quantities"] == []


def test_recommend_empty_note() -> None:
    note = _make_note(
        [
            NoteSection(key="social_history", title="Social History", text="Non-smoker"),
        ]
    )
    client = _make_client()

    recommender = PrescriptionRecommender()
    proposals = recommender.recommend(note, client)

    assert proposals == []
    client.request.assert_not_called()


def test_recommend_llm_error() -> None:
    note = _make_note(
        [
            NoteSection(
                key="assessment_and_plan",
                title="Assessment & Plan",
                text="Start amoxicillin.",
            ),
        ]
    )
    client = MagicMock()
    client.request.return_value = LlmResponse(
        code=HTTPStatus.INTERNAL_SERVER_ERROR,
        response="Server error",
        tokens=LlmTokens(prompt=0, generated=0),
    )

    recommender = PrescriptionRecommender()
    proposals = recommender.recommend(note, client)

    assert proposals == []


def test_recommend_llm_exception() -> None:
    note = _make_note(
        [
            NoteSection(
                key="assessment_and_plan",
                title="Assessment & Plan",
                text="Start amoxicillin.",
            ),
        ]
    )
    client = MagicMock()
    client.request.side_effect = Exception("Network error")

    recommender = PrescriptionRecommender()
    proposals = recommender.recommend(note, client)

    assert proposals == []


def test_recommend_malformed_response() -> None:
    note = _make_note(
        [
            NoteSection(
                key="assessment_and_plan",
                title="Assessment & Plan",
                text="Start amoxicillin.",
            ),
        ]
    )
    client = MagicMock()
    client.request.return_value = LlmResponse(
        code=HTTPStatus.OK,
        response="not valid json",
        tokens=LlmTokens(prompt=100, generated=50),
    )

    recommender = PrescriptionRecommender()
    proposals = recommender.recommend(note, client)

    assert proposals == []


@patch("hyperscribe.scribe.recommendations.prescription._resolve_prescription")
def test_recommend_multiple_prescriptions(mock_resolve: MagicMock) -> None:
    mock_resolve.side_effect = [
        MedicationDetail(fdb_code="111", description="Sumatriptan 50mg", quantities=[]),
        MedicationDetail(fdb_code="222", description="Amoxicillin 500mg", quantities=[]),
    ]

    note = _make_note(
        [
            NoteSection(
                key="assessment_and_plan",
                title="Assessment & Plan",
                text="Start sumatriptan 50mg and amoxicillin 500mg.",
            ),
        ]
    )
    client = _make_client(
        {
            "prescriptions": [
                {"medicationName": "Sumatriptan 50mg", "sig": "PRN", "keywords": "sumatriptan"},
                {"medicationName": "Amoxicillin 500mg", "sig": "TID x 10 days", "keywords": "amoxicillin"},
            ]
        }
    )

    recommender = PrescriptionRecommender()
    proposals = recommender.recommend(note, client)

    assert len(proposals) == 2
    assert proposals[0].display == "Sumatriptan 50mg"
    assert proposals[0].data["fdb_code"] == "111"
    assert proposals[1].display == "Amoxicillin 500mg"
    assert proposals[1].data["fdb_code"] == "222"


@patch("hyperscribe.scribe.recommendations.prescription._resolve_prescription")
def test_recommend_optional_fields_default_none(mock_resolve: MagicMock) -> None:
    mock_resolve.return_value = None

    note = _make_note(
        [
            NoteSection(key="plan", title="Plan", text="Start medication X."),
        ]
    )
    client = _make_client(
        {
            "prescriptions": [
                {
                    "medicationName": "Medication X",
                    "sig": "Take as directed",
                    "keywords": "medx",
                },
            ]
        }
    )

    recommender = PrescriptionRecommender()
    proposals = recommender.recommend(note, client)

    assert len(proposals) == 1
    assert proposals[0].data["days_supply"] is None
    assert proposals[0].data["quantity_to_dispense"] is None
    assert proposals[0].data["refills"] is None


@patch("hyperscribe.scribe.recommendations.prescription._resolve_prescription")
def test_recommend_from_prescription_section(mock_resolve: MagicMock) -> None:
    """Nabla may return a dedicated 'prescription' section with Rx details."""
    mock_resolve.return_value = MedicationDetail(
        fdb_code="55555", description="Excedrin Extra Strength Tablet", quantities=[]
    )

    note = _make_note(
        [
            NoteSection(
                key="prescription",
                title="Prescription",
                text="- Excedrin, daily for headache management",
            ),
        ]
    )
    client = _make_client(
        {
            "prescriptions": [
                {
                    "medicationName": "Excedrin",
                    "sig": "Take daily for headache management",
                    "keywords": "excedrin",
                },
            ]
        }
    )

    recommender = PrescriptionRecommender()
    proposals = recommender.recommend(note, client)

    assert len(proposals) == 1
    assert proposals[0].command_type == "prescribe"
    assert proposals[0].display == "Excedrin Extra Strength Tablet"
    assert proposals[0].data["fdb_code"] == "55555"
    client.request.assert_called_once()
