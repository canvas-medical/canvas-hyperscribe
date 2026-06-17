from __future__ import annotations

import json
from http import HTTPStatus

from logger import log

from canvas_sdk.clients.llms.libraries import LlmAnthropic

from hyperscribe.scribe.backend.models import ClinicalNote, CommandProposal, NoteSection, Transcript
from hyperscribe.scribe.recommendations.base import BaseRecommender
from hyperscribe.scribe.recommendations.schemas import ReferRecommendationList

_RELEVANT_KEYS = {"assessment_and_plan", "plan", "history_of_present_illness"}

# A referral is auto-signed on insert (see ReferParser.post_originate_effects), and
# Canvas core requires a recipient and a clinical question to sign it. Since these
# are generic referrals (no provider lookup), supply a placeholder recipient and a
# neutral default clinical question so the command is insert/sign-ready; the provider
# can replace the recipient and adjust the clinical question in the UI.
_DEFAULT_CLINICAL_QUESTION = "Assistance with Ongoing Management"
_PLACEHOLDER_LAST_NAME = "(TBD)"  # non-empty recipient, mirrors the science "(TBD)" convention

_SYSTEM_PROMPT = (
    "You are a clinical data extraction assistant. "
    "Extract only referrals the provider intends to make from the clinical note sections below. "
    "A referral is when the provider wants to send the patient to another specialist, practice, "
    "or provider for evaluation, consultation, or ongoing management. "
    "Look for phrases like 'refer to', 'referral to', 'consult with', 'send to', "
    "'evaluation by', or mentions of scheduling with a specialist. "
    "Do NOT include follow-up appointments with the same provider — those are not referrals. "
    "For each referral, extract the specialty, the condition/problem the referral addresses "
    "(copy the problem name verbatim from the note's assessment/plan), the clinical question "
    "category, priority, and reason."
)


def _build_user_prompt(sections: list[NoteSection]) -> str:
    parts: list[str] = []
    for section in sections:
        parts.append(f"## {section.title}\n{section.text}")
    return "\n\n".join(parts)


class ReferRecommender(BaseRecommender):
    def recommend(
        self, note: ClinicalNote, client: LlmAnthropic, transcript: Transcript | None = None
    ) -> list[CommandProposal]:
        sections = [s for s in note.sections if s.key.lower() in _RELEVANT_KEYS and s.text.strip()]
        if not sections:
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
            # Do not log response.response: it is derived from the note and may contain PHI.
            log.info(
                f"LLM returned {response.code} for refer recommendations "
                f"(response length: {len(response.response or '')})"
            )
            return []

        try:
            parsed = ReferRecommendationList.model_validate(json.loads(response.response))
        except Exception:
            # Do not log response.response: it is derived from the note and may contain PHI.
            log.exception(f"Failed to parse refer LLM response (response length: {len(response.response or '')})")
            return []

        proposals: list[CommandProposal] = []
        for ref in parsed.referrals:
            specialty = (ref.specialty or "").strip()
            if not specialty:
                continue
            indication = (ref.indication or "").strip() or None
            # Recommend a generic referral to the specialty only — no automatic
            # science-service provider lookup. A placeholder recipient keeps the
            # command insert/sign-ready (the provider can replace it in the UI),
            # and the indication is resolved to a validated diagnosis code
            # downstream (see _referral_diagnosis.link_referral_diagnoses).
            proposals.append(
                CommandProposal(
                    command_type="refer",
                    display=specialty,
                    data={
                        "service_provider": {
                            "first_name": "",
                            "last_name": _PLACEHOLDER_LAST_NAME,
                            "specialty": specialty,
                            "practice_name": specialty,
                        },
                        "refer_to_display": specialty,
                        "indication": indication,
                        "clinical_question": ref.clinical_question or _DEFAULT_CLINICAL_QUESTION,
                        "priority": ref.priority or "Routine",
                        "notes_to_specialist": ref.reason or indication or f"Referral to {specialty}",
                    },
                    section_key="_recommended",
                )
            )
        return proposals
