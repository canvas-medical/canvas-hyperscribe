from __future__ import annotations

from logger import log

from canvas_sdk.clients.llms.libraries import LlmAnthropic
from canvas_sdk.clients.llms.structures.settings import LlmSettingsAnthropic

from hyperscribe.scribe.backend.models import ClinicalNote, CommandProposal
from hyperscribe.scribe.recommendations.allergy import AllergyRecommender
from hyperscribe.scribe.recommendations.base import BaseRecommender
from hyperscribe.scribe.recommendations.medication_statement import MedicationRecommender

_RECOMMENDERS: list[BaseRecommender] = [MedicationRecommender(), AllergyRecommender()]

_MODEL = "claude-sonnet-4-5-20250929"


def _make_settings(api_key: str) -> LlmSettingsAnthropic:
    return LlmSettingsAnthropic(
        api_key=api_key,
        model=_MODEL,
        temperature=0.0,
        max_tokens=4096,
    )


def recommend_commands(note: ClinicalNote, api_key: str) -> list[CommandProposal]:
    """Run all recommenders against the clinical note and return proposals."""
    proposals: list[CommandProposal] = []
    for recommender in _RECOMMENDERS:
        try:
            client = LlmAnthropic(_make_settings(api_key))
            proposals.extend(recommender.recommend(note, client))
        except Exception:
            log.exception(f"Recommender {type(recommender).__name__} failed")
    return proposals
