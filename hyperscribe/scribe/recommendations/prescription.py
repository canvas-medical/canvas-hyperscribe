from __future__ import annotations

import json
from http import HTTPStatus

from logger import log

from canvas_sdk.clients.llms.libraries import LlmAnthropic

from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.scribe.backend.models import ClinicalNote, CommandProposal, NoteSection
from hyperscribe.scribe.recommendations.base import BaseRecommender
from hyperscribe.scribe.recommendations.schemas import PrescriptionRecommendationList
from hyperscribe.structures.medication_detail import MedicationDetail

_RELEVANT_KEYS = {"assessment_and_plan", "plan", "history_of_present_illness", "prescription"}

_SYSTEM_PROMPT = (
    "You are a clinical data extraction assistant. "
    "Extract only NEW prescriptions the provider intends to write from the clinical note sections below. "
    "Do NOT include medications the patient is already taking, continuing, "
    "or that are part of their medication history "
    "— those are medication statements, not new prescriptions. "
    "Only include medications that are being newly prescribed or started during this visit. "
    "For each prescription, provide the full medication name with strength/form, the sig (directions), "
    "days supply and quantity to dispense if mentioned, number of refills if mentioned, "
    "and a comma-separated list of search keywords (synonyms, brand/generic names) for database lookup (max 5)."
)


def _build_user_prompt(sections: list[NoteSection]) -> str:
    parts: list[str] = []
    for section in sections:
        parts.append(f"## {section.title}\n{section.text}")
    return "\n\n".join(parts)


def _resolve_prescription(
    keywords: str, cache: dict[str, MedicationDetail | None] | None = None
) -> MedicationDetail | None:
    """Search CanvasScience for the best medication match using the keyword list."""
    if cache is None:
        cache = {}
    for keyword in keywords.split(","):
        keyword = keyword.strip()
        if not keyword:
            continue
        key = keyword.lower()
        if key not in cache:
            results = CanvasScience.medication_details([keyword])
            cache[key] = results[0] if results else None
        if cache[key] is not None:
            return cache[key]
    return None


class PrescriptionRecommender(BaseRecommender):
    def recommend(self, note: ClinicalNote, client: LlmAnthropic) -> list[CommandProposal]:
        all_keys = [s.key for s in note.sections]
        log.info(f"PrescriptionRecommender: note section keys={all_keys}, filtering by {_RELEVANT_KEYS}")
        sections = [s for s in note.sections if s.key.lower() in _RELEVANT_KEYS and s.text.strip()]
        if not sections:
            log.info("PrescriptionRecommender: no matching sections, skipping")
            return []

        client.reset_prompts()
        client.set_system_prompt([_SYSTEM_PROMPT])
        client.set_user_prompt([_build_user_prompt(sections)])
        client.set_schema(PrescriptionRecommendationList)

        try:
            response = client.request()
        except Exception:
            log.exception("LLM request failed for prescription recommendations")
            return []

        if response.code != HTTPStatus.OK:
            log.info(f"LLM returned {response.code} for prescription recommendations: {response.response}")
            return []

        try:
            parsed = PrescriptionRecommendationList.model_validate(json.loads(response.response))
        except Exception:
            log.exception(f"Failed to parse prescription LLM response: {response.response}")
            return []

        lookup_cache: dict[str, MedicationDetail | None] = {}
        proposals: list[CommandProposal] = []
        for med in parsed.prescriptions:
            detail = _resolve_prescription(med.keywords, lookup_cache)
            fdb_code: str | None = None
            display = med.medication_name
            quantities: list[dict[str, str]] = []
            if detail:
                fdb_code = detail.fdb_code
                display = detail.description
                quantities = [q._asdict() for q in detail.quantities]

            proposals.append(
                CommandProposal(
                    command_type="prescribe",
                    display=display,
                    data={
                        "fdb_code": fdb_code,
                        "medication_text": display,
                        "sig": med.sig,
                        "days_supply": med.days_supply,
                        "quantity_to_dispense": med.quantity_to_dispense,
                        "refills": med.refills,
                        "quantities": quantities,
                    },
                    section_key="_recommended",
                )
            )
        return proposals
