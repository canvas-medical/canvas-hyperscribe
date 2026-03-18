from __future__ import annotations

import json
from http import HTTPStatus

from logger import log

from canvas_sdk.clients.llms.libraries import LlmAnthropic

from hyperscribe.scribe.backend.models import ClinicalNote, CommandProposal, NoteSection
from hyperscribe.scribe.contacts import search_refer_providers
from hyperscribe.scribe.recommendations.base import BaseRecommender
from hyperscribe.scribe.recommendations.schemas import ReferRecommendationList

_RELEVANT_KEYS = {"assessment_and_plan", "plan", "history_of_present_illness"}

_SYSTEM_PROMPT = (
    "You are a clinical data extraction assistant. "
    "Extract only referrals the provider intends to make from the clinical note sections below. "
    "A referral is when the provider wants to send the patient to another specialist, practice, "
    "or provider for evaluation, consultation, or ongoing management. "
    "Look for phrases like 'refer to', 'referral to', 'consult with', 'send to', "
    "'evaluation by', or mentions of scheduling with a specialist. "
    "Do NOT include follow-up appointments with the same provider — those are not referrals. "
    "For each referral, extract the specialty, provider/practice name if mentioned, "
    "clinical question category, priority, and reason."
)


def _build_user_prompt(sections: list[NoteSection]) -> str:
    parts: list[str] = []
    for section in sections:
        parts.append(f"## {section.title}\n{section.text}")
    return "\n\n".join(parts)


class ReferRecommender(BaseRecommender):
    def recommend(self, note: ClinicalNote, client: LlmAnthropic) -> list[CommandProposal]:
        all_keys = [s.key for s in note.sections]
        log.info(f"ReferRecommender: note section keys={all_keys}, filtering by {_RELEVANT_KEYS}")
        sections = [s for s in note.sections if s.key.lower() in _RELEVANT_KEYS and s.text.strip()]
        if not sections:
            log.info("ReferRecommender: no matching sections, skipping")
            return []

        client.reset_prompts()
        client.set_system_prompt([_SYSTEM_PROMPT])
        client.set_user_prompt([_build_user_prompt(sections)])
        client.set_schema(ReferRecommendationList)

        try:
            response = client.request()
        except Exception:
            log.exception("LLM request failed for refer recommendations")
            return []

        if response.code != HTTPStatus.OK:
            log.info(f"LLM returned {response.code} for refer recommendations: {response.response}")
            return []

        try:
            parsed = ReferRecommendationList.model_validate(json.loads(response.response))
        except Exception:
            log.exception(f"Failed to parse refer LLM response: {response.response}")
            return []
        proposals: list[CommandProposal] = []
        for ref in parsed.referrals:
            search_term = ref.specialty or ""
            if not search_term:
                continue

            results = search_refer_providers(search_term)
            # Skip TBD placeholder contacts — they aren't real providers.
            valid = [r for r in results if "(TBD)" not in (r.get("name") or "")]
            if valid:
                match = valid[0]
                display = match["name"]
                proposals.append(
                    CommandProposal(
                        command_type="refer",
                        display=display or search_term,
                        data={
                            "service_provider": match["data"],
                            "refer_to_display": display or search_term,
                            "clinical_question": ref.clinical_question or None,
                            "priority": ref.priority or "Routine",
                            "notes_to_specialist": ref.reason or None,
                        },
                        section_key="_recommended",
                    )
                )
            else:
                log.info(f"ReferRecommender: no contacts found for '{search_term}', adding as incomplete")
                proposals.append(
                    CommandProposal(
                        command_type="refer",
                        display=search_term,
                        data={
                            "clinical_question": ref.clinical_question or None,
                            "priority": ref.priority or "Routine",
                            "notes_to_specialist": ref.reason or None,
                        },
                        section_key="_recommended",
                    )
                )
        return proposals
