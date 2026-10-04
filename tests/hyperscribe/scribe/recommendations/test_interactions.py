from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from hyperscribe.scribe.recommendations.interactions import (
    _check_allergy_interactions,
    _check_drug_interactions,
    _get_patient_allergies,
    _get_patient_medications,
    _resolve_med_id_from_name,
    _resolve_med_id_from_ndc,
    check_recommendation_interactions,
    check_single_medication_interactions,
)


# ── _resolve_med_id_from_ndc ──


@patch("hyperscribe.scribe.recommendations.interactions.ontologies_http")
def test_resolve_med_id_from_ndc_success(mock_http: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"med_medication_id": 12345}
    mock_http.get_json.return_value = mock_resp

    result = _resolve_med_id_from_ndc("00123456789")
    assert result == "12345"
    mock_http.get_json.assert_called_once_with("/fdb/ndc-to-medication/00123456789/")


@patch("hyperscribe.scribe.recommendations.interactions.ontologies_http")
def test_resolve_med_id_from_ndc_empty(mock_http: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {}
    mock_http.get_json.return_value = mock_resp

    result = _resolve_med_id_from_ndc("00000000000")
    assert result is None


@patch("hyperscribe.scribe.recommendations.interactions.ontologies_http")
def test_resolve_med_id_from_ndc_exception(mock_http: MagicMock) -> None:
    mock_http.get_json.side_effect = Exception("network error")
    result = _resolve_med_id_from_ndc("00123456789")
    assert result is None


# ── _resolve_med_id_from_name ──


@patch("hyperscribe.scribe.recommendations.interactions.ontologies_http")
def test_resolve_med_id_from_name_success(mock_http: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": [{"med_medication_id": 67890}]}
    mock_http.get_json.return_value = mock_resp

    result = _resolve_med_id_from_name("Lisinopril")
    assert result == "67890"


@patch("hyperscribe.scribe.recommendations.interactions.ontologies_http")
def test_resolve_med_id_from_name_no_results(mock_http: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": []}
    mock_http.get_json.return_value = mock_resp

    result = _resolve_med_id_from_name("NonExistentDrug")
    assert result is None


@patch("hyperscribe.scribe.recommendations.interactions.ontologies_http")
def test_resolve_med_id_from_name_exception(mock_http: MagicMock) -> None:
    mock_http.get_json.side_effect = Exception("network error")
    result = _resolve_med_id_from_name("Lisinopril")
    assert result is None


# ── _get_patient_medications ──


@patch("hyperscribe.scribe.recommendations.interactions.Medication")
def test_get_patient_medications_with_fdb_coding(mock_med_model: MagicMock) -> None:
    coding = MagicMock()
    coding.display = "Lisinopril 10mg"
    coding.system = "http://www.fdbhealth.com/"
    coding.code = "111"

    med = MagicMock()
    med.id = "med-uuid-1"
    med.codings.all.return_value = [coding]

    qs = MagicMock()
    qs.active.return_value = qs
    qs.prefetch_related.return_value = [med]
    mock_med_model.objects.for_patient.return_value = qs

    result = _get_patient_medications("patient-1")
    assert len(result) == 1
    assert result[0]["display"] == "Lisinopril 10mg"
    assert result[0]["med_medication_id"] == "111"


@patch("hyperscribe.scribe.recommendations.interactions._resolve_med_id_from_name")
@patch("hyperscribe.scribe.recommendations.interactions._resolve_med_id_from_ndc")
@patch("hyperscribe.scribe.recommendations.interactions.Medication")
def test_get_patient_medications_fallback_ndc(
    mock_med_model: MagicMock,
    mock_ndc: MagicMock,
    mock_name: MagicMock,
) -> None:
    coding = MagicMock()
    coding.display = "Metformin 500mg"
    coding.system = "http://rxnorm.info"
    coding.code = "rxn123"

    med = MagicMock()
    med.id = "med-uuid-2"
    med.national_drug_code = "12345678901"
    med.codings.all.return_value = [coding]

    qs = MagicMock()
    qs.active.return_value = qs
    qs.prefetch_related.return_value = [med]
    mock_med_model.objects.for_patient.return_value = qs

    mock_ndc.return_value = "222"

    result = _get_patient_medications("patient-1")
    assert len(result) == 1
    assert result[0]["med_medication_id"] == "222"
    mock_ndc.assert_called_once_with("12345678901")
    mock_name.assert_not_called()


@patch("hyperscribe.scribe.recommendations.interactions._resolve_med_id_from_name")
@patch("hyperscribe.scribe.recommendations.interactions._resolve_med_id_from_ndc")
@patch("hyperscribe.scribe.recommendations.interactions.Medication")
def test_get_patient_medications_fallback_name(
    mock_med_model: MagicMock,
    mock_ndc: MagicMock,
    mock_name: MagicMock,
) -> None:
    coding = MagicMock()
    coding.display = "Aspirin 81mg"
    coding.system = "http://rxnorm.info"
    coding.code = "rxn456"

    med = MagicMock()
    med.id = "med-uuid-3"
    med.national_drug_code = None
    med.codings.all.return_value = [coding]

    qs = MagicMock()
    qs.active.return_value = qs
    qs.prefetch_related.return_value = [med]
    mock_med_model.objects.for_patient.return_value = qs

    mock_ndc.return_value = None
    mock_name.return_value = "333"

    result = _get_patient_medications("patient-1")
    assert len(result) == 1
    assert result[0]["med_medication_id"] == "333"
    mock_name.assert_called_once_with("Aspirin 81mg")


@patch("hyperscribe.scribe.recommendations.interactions.Medication")
def test_get_patient_medications_no_display_skipped(mock_med_model: MagicMock) -> None:
    coding = MagicMock()
    coding.display = None
    coding.system = "http://www.fdbhealth.com/"
    coding.code = "111"

    med = MagicMock()
    med.id = "med-uuid-4"
    med.codings.all.return_value = [coding]

    qs = MagicMock()
    qs.active.return_value = qs
    qs.prefetch_related.return_value = [med]
    mock_med_model.objects.for_patient.return_value = qs

    result = _get_patient_medications("patient-1")
    assert len(result) == 0


# ── _get_patient_allergies ──


@patch("hyperscribe.scribe.recommendations.interactions.AllergyIntolerance")
def test_get_patient_allergies_success(mock_allergy_model: MagicMock) -> None:
    coding = MagicMock()
    coding.display = "Penicillin"
    coding.system = "http://www.fdbhealth.com/"
    coding.code = "allergy-1"

    allergy = MagicMock()
    allergy.id = "allergy-uuid-1"
    allergy.category = 2
    allergy.codings.all.return_value = [coding]

    qs = MagicMock()
    qs.filter.return_value = qs
    qs.prefetch_related.return_value = [allergy]
    mock_allergy_model.objects.for_patient.return_value = qs

    result = _get_patient_allergies("patient-1")
    assert len(result) == 1
    assert result[0]["display"] == "Penicillin"
    assert result[0]["allergen_concept_id"] == "allergy-1"
    assert result[0]["allergen_concept_type"] == "2"


@patch("hyperscribe.scribe.recommendations.interactions.AllergyIntolerance")
def test_get_patient_allergies_no_fdb_code(mock_allergy_model: MagicMock) -> None:
    coding = MagicMock()
    coding.display = "Sulfa"
    coding.system = "http://snomed.info"
    coding.code = "sn-123"

    allergy = MagicMock()
    allergy.id = "allergy-uuid-2"
    allergy.category = None
    allergy.codings.all.return_value = [coding]

    qs = MagicMock()
    qs.filter.return_value = qs
    qs.prefetch_related.return_value = [allergy]
    mock_allergy_model.objects.for_patient.return_value = qs

    result = _get_patient_allergies("patient-1")
    assert len(result) == 1
    assert result[0]["allergen_concept_id"] == ""
    assert result[0]["allergen_concept_type"] == ""


# ── _check_drug_interactions ──


@patch("hyperscribe.scribe.recommendations.interactions.ontologies_http")
def test_check_drug_interactions_found(mock_http: MagicMock) -> None:
    interactions = [{"severity": "Severe", "drugName": "Warfarin"}]
    mock_resp = MagicMock()
    mock_resp.json.return_value = interactions
    mock_http.get_json.return_value = mock_resp

    result = _check_drug_interactions("100", ["200", "300"])
    assert result == {"interactions": interactions}

    call_url = mock_http.get_json.call_args[0][0]
    assert "/fdb/medication-list-interaction/" in call_url
    assert "consideredMedication" in call_url


@patch("hyperscribe.scribe.recommendations.interactions.ontologies_http")
def test_check_drug_interactions_dict_response(mock_http: MagicMock) -> None:
    response_data = {"interactions": [{"severity": "Moderate"}], "extra": "data"}
    mock_resp = MagicMock()
    mock_resp.json.return_value = response_data
    mock_http.get_json.return_value = mock_resp

    result = _check_drug_interactions("100", ["200"])
    assert result == response_data


def test_check_drug_interactions_empty_inputs() -> None:
    assert _check_drug_interactions("", ["200"]) == {"interactions": []}
    assert _check_drug_interactions("100", []) == {"interactions": []}


@patch("hyperscribe.scribe.recommendations.interactions.ontologies_http")
def test_check_drug_interactions_exception(mock_http: MagicMock) -> None:
    mock_http.get_json.side_effect = Exception("network error")
    result = _check_drug_interactions("100", ["200"])
    assert result["interactions"] == []
    assert "error" in result


# ── _check_allergy_interactions ──


@patch("hyperscribe.scribe.recommendations.interactions.ontologies_http")
def test_check_allergy_interactions_found(mock_http: MagicMock) -> None:
    interactions = [{"allergenName": "Penicillin", "ingredients": []}]
    mock_resp = MagicMock()
    mock_resp.json.return_value = interactions
    mock_http.get_json.return_value = mock_resp

    allergy_list = [{"allergen_concept_id": "A1", "allergen_concept_type": "2"}]
    result = _check_allergy_interactions("100", allergy_list)
    assert result == {"interactions": interactions}

    call_url = mock_http.get_json.call_args[0][0]
    assert "/fdb/medication-allergy/" in call_url


def test_check_allergy_interactions_empty_inputs() -> None:
    assert _check_allergy_interactions("", [{"allergen_concept_id": "A1", "allergen_concept_type": "2"}]) == {
        "interactions": []
    }
    assert _check_allergy_interactions("100", []) == {"interactions": []}


@patch("hyperscribe.scribe.recommendations.interactions.ontologies_http")
def test_check_allergy_interactions_exception(mock_http: MagicMock) -> None:
    mock_http.get_json.side_effect = Exception("network error")
    allergy_list = [{"allergen_concept_id": "A1", "allergen_concept_type": "2"}]
    result = _check_allergy_interactions("100", allergy_list)
    assert result["interactions"] == []
    assert "error" in result


# ── check_recommendation_interactions (orchestration) ──


def _make_prescription_rec(
    fdb_code: str | None = "999",
    medication_text: str = "TestDrug 50mg",
    **kwargs: Any,
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "command_type": "prescribe",
        "display": medication_text,
        "data": {"fdb_code": fdb_code, "medication_text": medication_text, **kwargs},
    }
    return rec


def _make_medication_statement_rec() -> dict[str, Any]:
    return {
        "command_type": "medication_statement",
        "display": "Existing Med",
        "data": {"medication_text": "Existing Med"},
    }


@patch("hyperscribe.scribe.recommendations.interactions._check_allergy_interactions")
@patch("hyperscribe.scribe.recommendations.interactions._check_drug_interactions")
@patch("hyperscribe.scribe.recommendations.interactions._get_patient_allergies")
@patch("hyperscribe.scribe.recommendations.interactions._get_patient_medications")
@patch("hyperscribe.scribe.recommendations.interactions.Note")
def test_check_recommendation_interactions_drug_interaction(
    mock_note_model: MagicMock,
    mock_get_meds: MagicMock,
    mock_get_allergies: MagicMock,
    mock_drug_check: MagicMock,
    mock_allergy_check: MagicMock,
) -> None:
    note = MagicMock()
    note.patient.id = "patient-1"
    mock_note_model.objects.select_related.return_value.get.return_value = note

    mock_get_meds.return_value = [{"id": "m1", "display": "Warfarin", "med_medication_id": "200"}]
    mock_get_allergies.return_value = []
    mock_drug_check.return_value = {"interactions": [{"severity": "Severe", "drugName": "Warfarin"}]}
    mock_allergy_check.return_value = {"interactions": []}

    recs = [_make_prescription_rec()]
    result = check_recommendation_interactions(recs, "note-uuid-1")

    assert len(result) == 1
    assert result[0]["recommendation_index"] == 0
    assert result[0]["medication_display"] == "TestDrug 50mg"
    assert len(result[0]["drug_interactions"]) == 1
    assert result[0]["allergy_interactions"] == []


@patch("hyperscribe.scribe.recommendations.interactions._check_allergy_interactions")
@patch("hyperscribe.scribe.recommendations.interactions._check_drug_interactions")
@patch("hyperscribe.scribe.recommendations.interactions._get_patient_allergies")
@patch("hyperscribe.scribe.recommendations.interactions._get_patient_medications")
@patch("hyperscribe.scribe.recommendations.interactions.Note")
def test_check_recommendation_interactions_allergy_interaction(
    mock_note_model: MagicMock,
    mock_get_meds: MagicMock,
    mock_get_allergies: MagicMock,
    mock_drug_check: MagicMock,
    mock_allergy_check: MagicMock,
) -> None:
    note = MagicMock()
    note.patient.id = "patient-1"
    mock_note_model.objects.select_related.return_value.get.return_value = note

    mock_get_meds.return_value = []
    mock_get_allergies.return_value = [
        {"id": "a1", "display": "Penicillin", "allergen_concept_id": "A100", "allergen_concept_type": "2"}
    ]
    mock_drug_check.return_value = {"interactions": []}
    mock_allergy_check.return_value = {"interactions": [{"allergenName": "Penicillin"}]}

    recs = [_make_prescription_rec()]
    result = check_recommendation_interactions(recs, "note-uuid-1")

    assert len(result) == 1
    assert len(result[0]["allergy_interactions"]) == 1
    assert result[0]["drug_interactions"] == []


@patch("hyperscribe.scribe.recommendations.interactions._check_allergy_interactions")
@patch("hyperscribe.scribe.recommendations.interactions._check_drug_interactions")
@patch("hyperscribe.scribe.recommendations.interactions._get_patient_allergies")
@patch("hyperscribe.scribe.recommendations.interactions._get_patient_medications")
@patch("hyperscribe.scribe.recommendations.interactions.Note")
def test_check_recommendation_interactions_no_interactions(
    mock_note_model: MagicMock,
    mock_get_meds: MagicMock,
    mock_get_allergies: MagicMock,
    mock_drug_check: MagicMock,
    mock_allergy_check: MagicMock,
) -> None:
    note = MagicMock()
    note.patient.id = "patient-1"
    mock_note_model.objects.select_related.return_value.get.return_value = note

    mock_get_meds.return_value = [{"id": "m1", "display": "Metformin", "med_medication_id": "300"}]
    mock_get_allergies.return_value = []
    mock_drug_check.return_value = {"interactions": []}
    mock_allergy_check.return_value = {"interactions": []}

    recs = [_make_prescription_rec()]
    result = check_recommendation_interactions(recs, "note-uuid-1")

    assert result == []


@patch("hyperscribe.scribe.recommendations.interactions._check_allergy_interactions")
@patch("hyperscribe.scribe.recommendations.interactions._check_drug_interactions")
@patch("hyperscribe.scribe.recommendations.interactions._get_patient_allergies")
@patch("hyperscribe.scribe.recommendations.interactions._get_patient_medications")
@patch("hyperscribe.scribe.recommendations.interactions.Note")
def test_check_recommendation_interactions_skips_medication_statement(
    mock_note_model: MagicMock,
    mock_get_meds: MagicMock,
    mock_get_allergies: MagicMock,
    mock_drug_check: MagicMock,
    mock_allergy_check: MagicMock,
) -> None:
    note = MagicMock()
    note.patient.id = "patient-1"
    mock_note_model.objects.select_related.return_value.get.return_value = note

    mock_get_meds.return_value = [{"id": "m1", "display": "Warfarin", "med_medication_id": "200"}]
    mock_get_allergies.return_value = []

    recs = [_make_medication_statement_rec()]
    result = check_recommendation_interactions(recs, "note-uuid-1")

    assert result == []
    mock_drug_check.assert_not_called()
    mock_allergy_check.assert_not_called()


@patch("hyperscribe.scribe.recommendations.interactions._resolve_med_id_from_name")
@patch("hyperscribe.scribe.recommendations.interactions._check_allergy_interactions")
@patch("hyperscribe.scribe.recommendations.interactions._check_drug_interactions")
@patch("hyperscribe.scribe.recommendations.interactions._get_patient_allergies")
@patch("hyperscribe.scribe.recommendations.interactions._get_patient_medications")
@patch("hyperscribe.scribe.recommendations.interactions.Note")
def test_check_recommendation_interactions_missing_fdb_code_resolves_by_name(
    mock_note_model: MagicMock,
    mock_get_meds: MagicMock,
    mock_get_allergies: MagicMock,
    mock_drug_check: MagicMock,
    mock_allergy_check: MagicMock,
    mock_resolve_name: MagicMock,
) -> None:
    note = MagicMock()
    note.patient.id = "patient-1"
    mock_note_model.objects.select_related.return_value.get.return_value = note

    mock_get_meds.return_value = [{"id": "m1", "display": "Warfarin", "med_medication_id": "200"}]
    mock_get_allergies.return_value = []
    mock_resolve_name.return_value = "555"
    mock_drug_check.return_value = {"interactions": [{"severity": "Moderate", "drugName": "Warfarin"}]}
    mock_allergy_check.return_value = {"interactions": []}

    recs = [_make_prescription_rec(fdb_code=None)]
    result = check_recommendation_interactions(recs, "note-uuid-1")

    assert len(result) == 1
    mock_resolve_name.assert_called_once_with("TestDrug 50mg")
    mock_drug_check.assert_called_once_with("555", ["200"])


def test_check_recommendation_interactions_empty_note_uuid() -> None:
    result = check_recommendation_interactions([_make_prescription_rec()], "")
    assert result == []


def test_check_recommendation_interactions_empty_recommendations() -> None:
    result = check_recommendation_interactions([], "note-uuid-1")
    assert result == []


@patch("hyperscribe.scribe.recommendations.interactions.Note")
def test_check_recommendation_interactions_note_not_found(mock_note_model: MagicMock) -> None:
    from canvas_sdk.v1.data.note import Note

    mock_note_model.DoesNotExist = Note.DoesNotExist
    mock_note_model.objects.select_related.return_value.get.side_effect = Note.DoesNotExist()

    result = check_recommendation_interactions([_make_prescription_rec()], "bad-uuid")
    assert result == []


@patch("hyperscribe.scribe.recommendations.interactions._check_allergy_interactions")
@patch("hyperscribe.scribe.recommendations.interactions._check_drug_interactions")
@patch("hyperscribe.scribe.recommendations.interactions._get_patient_allergies")
@patch("hyperscribe.scribe.recommendations.interactions._get_patient_medications")
@patch("hyperscribe.scribe.recommendations.interactions.Note")
def test_check_recommendation_interactions_no_fdb_code_no_resolve_skips(
    mock_note_model: MagicMock,
    mock_get_meds: MagicMock,
    mock_get_allergies: MagicMock,
    mock_drug_check: MagicMock,
    mock_allergy_check: MagicMock,
) -> None:
    """When fdb_code is None and name resolution also fails, skip the medication."""
    note = MagicMock()
    note.patient.id = "patient-1"
    mock_note_model.objects.select_related.return_value.get.return_value = note

    mock_get_meds.return_value = [{"id": "m1", "display": "Warfarin", "med_medication_id": "200"}]
    mock_get_allergies.return_value = []

    with patch(
        "hyperscribe.scribe.recommendations.interactions._resolve_med_id_from_name",
        return_value=None,
    ):
        recs = [_make_prescription_rec(fdb_code=None)]
        result = check_recommendation_interactions(recs, "note-uuid-1")

    assert result == []
    mock_drug_check.assert_not_called()
    mock_allergy_check.assert_not_called()


# ── check_single_medication_interactions ──


@patch("hyperscribe.scribe.recommendations.interactions._check_allergy_interactions")
@patch("hyperscribe.scribe.recommendations.interactions._check_drug_interactions")
@patch("hyperscribe.scribe.recommendations.interactions._get_patient_allergies")
@patch("hyperscribe.scribe.recommendations.interactions._get_patient_medications")
@patch("hyperscribe.scribe.recommendations.interactions.Note")
def test_check_single_medication_interactions_with_fdb_code(
    mock_note_model: MagicMock,
    mock_get_meds: MagicMock,
    mock_get_allergies: MagicMock,
    mock_drug_check: MagicMock,
    mock_allergy_check: MagicMock,
) -> None:
    note = MagicMock()
    note.patient.id = "patient-1"
    mock_note_model.objects.select_related.return_value.get.return_value = note

    mock_get_meds.return_value = [{"id": "m1", "display": "Warfarin", "med_medication_id": "200"}]
    mock_get_allergies.return_value = [
        {"id": "a1", "display": "Penicillin", "allergen_concept_id": "A100", "allergen_concept_type": "2"}
    ]
    mock_drug_check.return_value = {"interactions": [{"severity": "Severe", "drugName": "Warfarin"}]}
    mock_allergy_check.return_value = {"interactions": [{"allergenName": "Penicillin"}]}

    result = check_single_medication_interactions("999", "TestDrug", "note-uuid-1")

    assert len(result["drug_interactions"]) == 1
    assert len(result["allergy_interactions"]) == 1
    assert result["medication_display"] == "TestDrug"
    mock_drug_check.assert_called_once_with("999", ["200"])


@patch("hyperscribe.scribe.recommendations.interactions._resolve_med_id_from_name")
@patch("hyperscribe.scribe.recommendations.interactions._check_allergy_interactions")
@patch("hyperscribe.scribe.recommendations.interactions._check_drug_interactions")
@patch("hyperscribe.scribe.recommendations.interactions._get_patient_allergies")
@patch("hyperscribe.scribe.recommendations.interactions._get_patient_medications")
@patch("hyperscribe.scribe.recommendations.interactions.Note")
def test_check_single_medication_interactions_no_fdb_resolves_by_name(
    mock_note_model: MagicMock,
    mock_get_meds: MagicMock,
    mock_get_allergies: MagicMock,
    mock_drug_check: MagicMock,
    mock_allergy_check: MagicMock,
    mock_resolve_name: MagicMock,
) -> None:
    note = MagicMock()
    note.patient.id = "patient-1"
    mock_note_model.objects.select_related.return_value.get.return_value = note

    mock_get_meds.return_value = [{"id": "m1", "display": "Warfarin", "med_medication_id": "200"}]
    mock_get_allergies.return_value = []
    mock_resolve_name.return_value = "555"
    mock_drug_check.return_value = {"interactions": []}
    mock_allergy_check.return_value = {"interactions": []}

    result = check_single_medication_interactions(None, "Amoxicillin", "note-uuid-1")

    mock_resolve_name.assert_called_once_with("Amoxicillin")
    mock_drug_check.assert_called_once_with("555", ["200"])


def test_check_single_medication_interactions_empty_note_uuid() -> None:
    result = check_single_medication_interactions("999", "TestDrug", "")
    assert result["drug_interactions"] == []
    assert result["allergy_interactions"] == []


@patch("hyperscribe.scribe.recommendations.interactions.Note")
def test_check_single_medication_interactions_note_not_found(mock_note_model: MagicMock) -> None:
    from canvas_sdk.v1.data.note import Note

    mock_note_model.DoesNotExist = Note.DoesNotExist
    mock_note_model.objects.select_related.return_value.get.side_effect = Note.DoesNotExist()

    result = check_single_medication_interactions("999", "TestDrug", "bad-uuid")
    assert result["drug_interactions"] == []
    assert result["allergy_interactions"] == []


@patch("hyperscribe.scribe.recommendations.interactions._resolve_med_id_from_name")
@patch("hyperscribe.scribe.recommendations.interactions.Note")
def test_check_single_medication_interactions_no_resolve_returns_empty(
    mock_note_model: MagicMock,
    mock_resolve_name: MagicMock,
) -> None:
    note = MagicMock()
    note.patient.id = "patient-1"
    mock_note_model.objects.select_related.return_value.get.return_value = note
    mock_resolve_name.return_value = None

    result = check_single_medication_interactions(None, "UnknownDrug", "note-uuid-1")
    assert result["drug_interactions"] == []
    assert result["allergy_interactions"] == []
