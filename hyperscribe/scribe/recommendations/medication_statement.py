from __future__ import annotations

import json
from http import HTTPStatus

from logger import log

from canvas_sdk.clients.llms.libraries import LlmAnthropic
from canvas_sdk.commands.constants import CodeSystems

from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.scribe.backend.models import ClinicalNote, CommandProposal, NoteSection
from hyperscribe.scribe.recommendations.base import BaseRecommender
from hyperscribe.scribe.recommendations.schemas import MedicationRecommendationList

_RELEVANT_KEYS = {"current_medications", "history_of_present_illness", "assessment_and_plan", "plan"}

_SYSTEM_PROMPT = (
    "You are a clinical data extraction assistant. "
    "Extract all medications mentioned in the clinical note sections below. "
    "Include both currently prescribed medications and any new medications the provider plans to start. "
    "For each medication, provide the full name with strength, the sig (directions), "
    "and a comma-separated list of search keywords (synonyms, brand/generic names) for database lookup (max 5)."
)


def _build_user_prompt(sections: list[NoteSection]) -> str:
    parts: list[str] = []
    for section in sections:
        parts.append(f"## {section.title}\n{section.text}")
    return "\n\n".join(parts)


def _resolve_medication(keywords: str) -> dict[str, str] | None:
    """Search CanvasScience for the best medication match using the keyword list."""
    for keyword in keywords.split(","):
        keyword = keyword.strip()
        if not keyword:
            continue
        results = CanvasScience.medication_details([keyword])
        if results:
            return {"fdb_code": results[0].fdb_code, "description": results[0].description}
    return None


class MedicationRecommender(BaseRecommender):
    def recommend(self, note: ClinicalNote, client: LlmAnthropic) -> list[CommandProposal]:
        all_keys = [s.key for s in note.sections]
        log.info(f"MedicationRecommender: note section keys={all_keys}, filtering by {_RELEVANT_KEYS}")
        sections = [s for s in note.sections if s.key in _RELEVANT_KEYS and s.text.strip()]
        if not sections:
            log.info("MedicationRecommender: no matching sections, skipping")
            return []

        client.reset_prompts()
        client.set_system_prompt([_SYSTEM_PROMPT])
        client.set_user_prompt([_build_user_prompt(sections)])
        client.set_schema(MedicationRecommendationList)

        try:
            response = client.request()
        except Exception:
            log.exception("LLM request failed for medication recommendations")
            return []

        if response.code != HTTPStatus.OK:
            log.info(f"LLM returned {response.code} for medication recommendations: {response.response}")
            return []

        try:
            parsed = MedicationRecommendationList.model_validate(json.loads(response.response))
        except Exception:
            log.exception(f"Failed to parse medication LLM response: {response.response}")
            return []

        proposals: list[CommandProposal] = []
        for med in parsed.medications:
            resolved = _resolve_medication(med.keywords)
            fdb_code: dict[str, str] | None = None
            display = med.medication_name
            if resolved:
                fdb_code = {
                    "system": CodeSystems.FDB,
                    "code": resolved["fdb_code"],
                    "display": resolved["description"],
                }
                display = resolved["description"]

            proposals.append(
                CommandProposal(
                    command_type="medication_statement",
                    display=display,
                    data={
                        "medication_text": display,
                        "fdb_code": fdb_code,
                        "sig": med.sig,
                    },
                    section_key="_recommended",
                )
            )
        return proposals
