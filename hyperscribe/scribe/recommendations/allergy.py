from __future__ import annotations

import json
from http import HTTPStatus

from logger import log

from canvas_sdk.clients.llms.libraries import LlmAnthropic
from canvas_sdk.commands.commands.allergy import AllergenType

from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.scribe.backend.models import ClinicalNote, CommandProposal, NoteSection
from hyperscribe.scribe.recommendations.base import BaseRecommender
from hyperscribe.scribe.recommendations.schemas import AllergyRecommendationList

_RELEVANT_KEYS = {"allergies"}

_SYSTEM_PROMPT = (
    "You are a clinical data extraction assistant. "
    "Extract all allergies mentioned in the clinical note sections below. "
    "For each allergy, provide the allergen name, the reaction description, "
    "severity (mild, moderate, or severe if stated, otherwise null), "
    "and a comma-separated list of search keywords (synonyms, drug class names) for database lookup (max 5)."
)


def _build_user_prompt(sections: list[NoteSection]) -> str:
    parts: list[str] = []
    for section in sections:
        parts.append(f"## {section.title}\n{section.text}")
    return "\n\n".join(parts)


def _resolve_allergy(keywords: str, cache: dict[str, dict[str, int] | None] | None = None) -> dict[str, int] | None:
    """Search CanvasScience for the best allergy match using the keyword list."""
    if cache is None:
        cache = {}
    for keyword in keywords.split(","):
        keyword = keyword.strip()
        if not keyword:
            continue
        key = keyword.lower()
        if key not in cache:
            results = CanvasScience.search_allergy(
                [keyword],
                [AllergenType.ALLERGEN_GROUP, AllergenType.MEDICATION, AllergenType.INGREDIENT],
            )
            cache[key] = (
                {"concept_id": results[0].concept_id_value, "concept_id_type": results[0].concept_id_type}
                if results
                else None
            )
        if cache[key] is not None:
            return cache[key]
    return None


class AllergyRecommender(BaseRecommender):
    def recommend(self, note: ClinicalNote, client: LlmAnthropic) -> list[CommandProposal]:
        all_keys = [s.key for s in note.sections]
        log.info(f"AllergyRecommender: note section keys={all_keys}, filtering by {_RELEVANT_KEYS}")
        sections = [s for s in note.sections if s.key.lower() in _RELEVANT_KEYS and s.text.strip()]
        if not sections:
            log.info("AllergyRecommender: no matching sections, skipping")
            return []

        client.reset_prompts()
        client.set_system_prompt([_SYSTEM_PROMPT])
        client.set_user_prompt([_build_user_prompt(sections)])
        client.set_schema(AllergyRecommendationList)

        try:
            response = client.request()
        except Exception:
            log.exception("LLM request failed for allergy recommendations")
            return []

        if response.code != HTTPStatus.OK:
            log.info(f"LLM returned {response.code} for allergy recommendations: {response.response}")
            return []

        try:
            parsed = AllergyRecommendationList.model_validate(json.loads(response.response))
        except Exception:
            log.exception(f"Failed to parse allergy LLM response: {response.response}")
            return []

        lookup_cache: dict[str, dict[str, int] | None] = {}
        proposals: list[CommandProposal] = []
        for allergy in parsed.allergies:
            resolved = _resolve_allergy(allergy.keywords, lookup_cache)
            concept_id: int | None = None
            concept_id_type: int | None = None
            if resolved:
                concept_id = resolved["concept_id"]
                concept_id_type = resolved["concept_id_type"]

            severity = allergy.severity if allergy.severity in {"mild", "moderate", "severe"} else None

            proposals.append(
                CommandProposal(
                    command_type="allergy",
                    display=allergy.allergen,
                    data={
                        "allergy_text": allergy.allergen,
                        "concept_id": concept_id,
                        "concept_id_type": concept_id_type,
                        "reaction": allergy.reaction,
                        "severity": severity,
                    },
                    section_key="_recommended",
                )
            )
        return proposals
