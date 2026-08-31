from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

from logger import log

from canvas_sdk.utils.http import ontologies_http
from canvas_sdk.v1.data.allergy_intolerance import AllergyIntolerance
from canvas_sdk.v1.data.medication import Medication
from canvas_sdk.v1.data.note import Note

FDB_SYSTEM = "http://www.fdbhealth.com/"


def _resolve_med_id_from_ndc(ndc: str) -> str | None:
    """Resolve an FDB MEDID from a National Drug Code via the ontologies service."""
    try:
        response = ontologies_http.get_json(f"/fdb/ndc-to-medication/{ndc}/")
        data = response.json()
        if data:
            return str(data.get("med_medication_id")) if data.get("med_medication_id") else None
    except Exception:
        log.exception(f"Error resolving MEDID from NDC {ndc}")
    return None


def _resolve_med_id_from_name(name: str) -> str | None:
    """Resolve an FDB MEDID by searching the medication name."""
    try:
        url = f"/fdb/grouped-medication/?{urlencode({'search': name})}"
        response = ontologies_http.get_json(url)
        data = response.json()
        if data:
            results = data.get("results", [])
            if results:
                return str(results[0].get("med_medication_id"))
    except Exception:
        log.exception(f"Error resolving MEDID from name {name}")
    return None


def _get_patient_medications(patient_id: str) -> list[dict[str, Any]]:
    """Get active medications for a patient with resolved FDB MEDIDs."""
    meds: list[dict[str, Any]] = []
    try:
        medications = Medication.objects.for_patient(patient_id).active().prefetch_related("codings")
        for med in medications:
            display = None
            fdb_code = None
            for coding in med.codings.all():
                if coding.display and not display:
                    display = coding.display
                if coding.system == FDB_SYSTEM and coding.code:
                    fdb_code = coding.code

            if not display:
                continue

            med_id = fdb_code
            if not med_id:
                try:
                    ndc = med.national_drug_code
                    if ndc:
                        med_id = _resolve_med_id_from_ndc(ndc)
                    if not med_id:
                        med_id = _resolve_med_id_from_name(display)
                except Exception:
                    log.exception(f"Error resolving MEDID for {display}")

            meds.append(
                {
                    "id": str(med.id),
                    "display": display,
                    "med_medication_id": med_id or "",
                }
            )
    except Exception:
        log.exception(f"Error fetching medications for patient {patient_id}")
    return meds


def _get_patient_allergies(patient_id: str) -> list[dict[str, Any]]:
    """Get committed allergies for a patient with FDB allergen concept IDs."""
    allergies: list[dict[str, Any]] = []
    try:
        allergy_records = (
            AllergyIntolerance.objects.for_patient(patient_id)
            .filter(
                committer__isnull=False,
                entered_in_error__isnull=True,
            )
            .prefetch_related("codings")
        )
        for allergy in allergy_records:
            display = None
            substance_code = None
            for coding in allergy.codings.all():
                if coding.display and not display:
                    display = coding.display
                if coding.system == FDB_SYSTEM and coding.code:
                    substance_code = coding.code

            if display:
                allergies.append(
                    {
                        "id": str(allergy.id),
                        "display": display,
                        "allergen_concept_id": substance_code or "",
                        "allergen_concept_type": (str(allergy.category) if allergy.category is not None else ""),
                    }
                )
    except Exception:
        log.exception(f"Error fetching allergies for patient {patient_id}")
    return allergies


def _check_drug_interactions(considered_med_id: str, existing_med_ids: list[str]) -> dict[str, Any]:
    """Check drug-drug interactions via /fdb/medication-list-interaction/."""
    if not considered_med_id or not existing_med_ids:
        return {"interactions": []}
    try:
        considered = json.dumps([[considered_med_id, "FDB"]], separators=(",", ":"))
        med_list = json.dumps(
            [[[mid, "FDB"]] for mid in existing_med_ids],
            separators=(",", ":"),
        )
        params = urlencode(
            {
                "consideredMedication": considered,
                "medicationList": med_list,
            }
        )
        url = f"/fdb/medication-list-interaction/?{params}"
        response = ontologies_http.get_json(url)
        data = response.json()
        if data is None:
            return {
                "interactions": [],
                "error": f"Ontologies returned status {response.status_code}",
            }
        if isinstance(data, list):
            return {"interactions": data}
        return data  # type: ignore[no-any-return]
    except Exception:
        log.exception("Error checking drug-drug interactions")
        return {"interactions": [], "error": "Could not retrieve drug-drug interactions."}


def _check_allergy_interactions(considered_med_id: str, allergy_list: list[dict[str, Any]]) -> dict[str, Any]:
    """Check drug-allergy interactions via /fdb/medication-allergy/."""
    if not considered_med_id or not allergy_list:
        return {"interactions": []}
    try:
        considered = json.dumps([[considered_med_id, "FDB"]], separators=(",", ":"))
        allergens = json.dumps(
            [[a["allergen_concept_id"], a["allergen_concept_type"]] for a in allergy_list],
            separators=(",", ":"),
        )
        params = urlencode(
            {
                "consideredMedication": considered,
                "allergyList": allergens,
            }
        )
        url = f"/fdb/medication-allergy/?{params}"
        response = ontologies_http.get_json(url)
        data = response.json()
        if data is None:
            return {
                "interactions": [],
                "error": f"Ontologies returned status {response.status_code}",
            }
        if isinstance(data, list):
            return {"interactions": data}
        return data  # type: ignore[no-any-return]
    except Exception:
        log.exception("Error checking drug-allergy interactions")
        return {"interactions": [], "error": "Could not retrieve drug-allergy interactions."}


def check_single_medication_interactions(
    fdb_code: str | None,
    medication_name: str,
    note_uuid: str,
) -> dict[str, Any]:
    """Check a single medication against a patient's existing meds/allergies.

    Used for on-demand checks when a provider adds or edits a prescription.
    Returns:
        {
            "drug_interactions": [...],
            "allergy_interactions": [...],
            "medication_display": str,
        }
    """
    if not note_uuid:
        return {"drug_interactions": [], "allergy_interactions": [], "medication_display": medication_name}

    try:
        note = Note.objects.select_related("patient").get(id=note_uuid)
    except Note.DoesNotExist:
        log.warning(f"Note {note_uuid} not found for interaction check")
        return {"drug_interactions": [], "allergy_interactions": [], "medication_display": medication_name}

    med_id = fdb_code or None
    if not med_id:
        med_id = _resolve_med_id_from_name(medication_name)
    if not med_id:
        return {"drug_interactions": [], "allergy_interactions": [], "medication_display": medication_name}

    patient_id = str(note.patient.id)
    existing_meds = _get_patient_medications(patient_id)
    existing_allergies = _get_patient_allergies(patient_id)

    existing_med_ids = [m["med_medication_id"] for m in existing_meds if m["med_medication_id"]]
    allergy_entries = [a for a in existing_allergies if a["allergen_concept_id"]]

    drug_result = _check_drug_interactions(med_id, existing_med_ids)
    allergy_result = _check_allergy_interactions(med_id, allergy_entries)

    return {
        "drug_interactions": drug_result.get("interactions", []),
        "allergy_interactions": allergy_result.get("interactions", []),
        "medication_display": medication_name,
    }


def check_recommendation_interactions(
    recommendations: list[dict[str, Any]],
    note_uuid: str,
) -> list[dict[str, Any]]:
    """Check recommended prescriptions against patient's existing meds/allergies.

    Returns a list of interaction warning dicts:
    [
        {
            "recommendation_index": int,
            "medication_display": str,
            "drug_interactions": [...],
            "allergy_interactions": [...],
        }
    ]
    """
    if not note_uuid or not recommendations:
        return []

    try:
        note = Note.objects.select_related("patient").get(id=note_uuid)
    except Note.DoesNotExist:
        log.warning(f"Note {note_uuid} not found for interaction check")
        return []

    patient_id = str(note.patient.id)
    existing_meds = _get_patient_medications(patient_id)
    existing_allergies = _get_patient_allergies(patient_id)

    existing_med_ids = [m["med_medication_id"] for m in existing_meds if m["med_medication_id"]]
    allergy_entries = [a for a in existing_allergies if a["allergen_concept_id"]]

    warnings: list[dict[str, Any]] = []
    for idx, rec in enumerate(recommendations):
        if rec.get("command_type") != "prescribe":
            continue

        data = rec.get("data", {})
        med_id = data.get("fdb_code") or None
        medication_display = data.get("medication_text", rec.get("display", ""))

        if not med_id:
            med_id = _resolve_med_id_from_name(medication_display)

        if not med_id:
            continue

        drug_result = _check_drug_interactions(med_id, existing_med_ids)
        allergy_result = _check_allergy_interactions(med_id, allergy_entries)

        drug_interactions = drug_result.get("interactions", [])
        allergy_interactions = allergy_result.get("interactions", [])

        if drug_interactions or allergy_interactions:
            warnings.append(
                {
                    "recommendation_index": idx,
                    "medication_display": medication_display,
                    "drug_interactions": drug_interactions,
                    "allergy_interactions": allergy_interactions,
                }
            )

    return warnings
