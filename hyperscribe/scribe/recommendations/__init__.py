from __future__ import annotations

from logger import log

from canvas_sdk.clients.llms.libraries import LlmAnthropic
from canvas_sdk.clients.llms.structures.settings import LlmSettingsAnthropic

from hyperscribe.scribe.backend.models import ClinicalNote, CommandProposal, Transcript
from hyperscribe.scribe.recommendations.allergy import AllergyRecommender
from hyperscribe.scribe.recommendations.base import BaseRecommender
from hyperscribe.scribe.recommendations.lab import LabRecommender
from hyperscribe.scribe.recommendations.medication_statement import MedicationRecommender
from hyperscribe.scribe.recommendations.prescription import PrescriptionRecommender
from hyperscribe.scribe.recommendations.refer import ReferRecommender
from hyperscribe.scribe.recommendations.task import TaskRecommender

_MODEL = "claude-sonnet-4-5-20250929"


def _make_settings(api_key: str) -> LlmSettingsAnthropic:
    return LlmSettingsAnthropic(
        api_key=api_key,
        model=_MODEL,
        temperature=0.0,
        max_tokens=4096,
    )


def _build_recommenders(zip_codes: list[str] | None = None) -> list[BaseRecommender]:
    return [
        MedicationRecommender(),
        AllergyRecommender(),
        PrescriptionRecommender(),
        ReferRecommender(zip_codes=zip_codes),
        LabRecommender(),
        TaskRecommender(),
    ]


def recommend_commands(
    note: ClinicalNote,
    api_key: str,
    zip_codes: list[str] | None = None,
    transcript: Transcript | None = None,
) -> list[CommandProposal]:
    """Run all recommenders against the clinical note and return proposals."""
    proposals: list[CommandProposal] = []
    for recommender in _build_recommenders(zip_codes):
        try:
            client = LlmAnthropic(_make_settings(api_key))
            proposals.extend(recommender.recommend(note, client, transcript=transcript))
        except Exception:
            log.exception(f"Recommender {type(recommender).__name__} failed")
    return proposals
