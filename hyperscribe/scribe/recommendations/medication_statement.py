from __future__ import annotations

import json
from http import HTTPStatus

from logger import log

from canvas_sdk.clients.llms.libraries import LlmAnthropic
from canvas_sdk.commands.constants import CodeSystems

from hyperscribe.scribe.backend.models import ClinicalNote, CommandProposal, NoteSection, Transcript
from hyperscribe.scribe.recommendations._medication_match import resolve_medication_detail, sanitize_sig
from hyperscribe.scribe.recommendations.base import BaseRecommender
from hyperscribe.scribe.recommendations.schemas import MedicationRecommendationList
from hyperscribe.structures.medication_detail import MedicationDetail

_RELEVANT_KEYS = {"current_medications", "history_of_present_illness", "assessment_and_plan", "plan"}

_SYSTEM_PROMPT = (
    "You are a clinical data extraction assistant. "
    "Extract all medications mentioned in the clinical note sections below. "
    "Include medications the patient is currently taking or that were mentioned as part of their medication history. "
    "Do NOT include medications that are being newly prescribed — only include existing/current medications. "
    "For each medication, provide the full name with strength, the sig (directions), "
    "and a comma-separated list of search keywords (synonyms, brand/generic names) for database lookup (max 5). "
    "CRITICAL: preserve the exact strength/dose as stated in the note (e.g. '20 mg'); "
    "never round it or substitute a different strength. "
    "If the note does not state directions for a medication, leave the sig null rather than "
    "guessing or inferring a frequency."
)


def _build_user_prompt(sections: list[NoteSection]) -> str:
    parts: list[str] = []
    for section in sections:
        parts.append(f"## {section.title}\n{section.text}")
    return "\n\n".join(parts)


def _resolve_medication(
    medication_name: str,
    keywords: str,
    cache: dict[str, list[MedicationDetail]] | None = None,
) -> MedicationDetail | None:
    """Resolve the stated medication to the FDB candidate matching its strength.

    Delegates to the shared strength-aware resolver so the medication-statement
    and prescription recommenders stay in sync.
    """
    return resolve_medication_detail(medication_name, keywords, cache)


class MedicationRecommender(BaseRecommender):
    def recommend(
        self, note: ClinicalNote, client: LlmAnthropic, transcript: Transcript | None = None
    ) -> list[CommandProposal]:
        all_keys = [s.key for s in note.sections]
        log.info(f"MedicationRecommender: note section keys={all_keys}, filtering by {_RELEVANT_KEYS}")
        sections = [s for s in note.sections if s.key.lower() in _RELEVANT_KEYS and s.text.strip()]
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
            # Do not log response.response: it is derived from the note and may contain PHI.
            log.info(
                f"LLM returned {response.code} for medication recommendations "
                f"(response length: {len(response.response or '')})"
            )
            return []

        try:
            parsed = MedicationRecommendationList.model_validate(json.loads(response.response))
        except Exception:
            # Do not log response.response: it is derived from the note and may contain PHI.
            log.exception(f"Failed to parse medication LLM response (response length: {len(response.response or '')})")
            return []

        lookup_cache: dict[str, list[MedicationDetail]] = {}
        proposals: list[CommandProposal] = []
        for med in parsed.medications:
            resolved = _resolve_medication(med.medication_name, med.keywords, lookup_cache)
            fdb_code: dict[str, str] | None = None
            display = med.medication_name
            if resolved:
                fdb_code = {
                    "system": CodeSystems.FDB,
                    "code": resolved.fdb_code,
                    "display": resolved.description,
                }
                display = resolved.description

            proposals.append(
                CommandProposal(
                    command_type="medication_statement",
                    display=display,
                    data={
                        "medication_text": display,
                        "fdb_code": fdb_code,
                        "sig": sanitize_sig(med.sig),
                    },
                    section_key="_recommended",
                )
            )
        return proposals
