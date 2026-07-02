from __future__ import annotations

import re

from logger import log

from canvas_sdk.clients.llms.libraries import LlmAnthropic
from canvas_sdk.clients.llms.structures.settings import LlmSettingsAnthropic

from hyperscribe.scribe.backend.models import ClinicalNote, CommandProposal, Transcript
from hyperscribe.scribe.recommendations.allergy import AllergyRecommender
from hyperscribe.scribe.recommendations.base import BaseRecommender
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


def prescription_dispense_enabled(allowlist_raw: str | None, provider_id: str | None) -> bool:
    """Whether the prescription dispense-field engine is enabled for this provider.

    The allowlist is a comma/space-separated list of staff keys (same tokenization
    as the other scribe staffer secrets). **Blank/unset -> enabled for all users**
    (fail-open, by product decision); otherwise enabled only when the note's
    provider is in the list.
    """
    allowed = re.findall(r"[A-Za-z0-9]+", allowlist_raw or "")
    if not allowed:
        return True
    return bool(provider_id) and str(provider_id) in allowed


def _build_recommenders(
    zip_codes: list[str] | None = None,
    dispense_engine_enabled: bool = True,
) -> list[BaseRecommender]:
    return [
        MedicationRecommender(),
        AllergyRecommender(),
        PrescriptionRecommender(dispense_engine_enabled=dispense_engine_enabled),
        # zip_codes is intentionally not passed: referrals are recommended
        # generically (specialty only), without a provider lookup.
        ReferRecommender(),
        TaskRecommender(),
    ]


def recommend_commands(
    note: ClinicalNote,
    api_key: str,
    zip_codes: list[str] | None = None,
    transcript: Transcript | None = None,
    dispense_engine_enabled: bool = True,
) -> list[CommandProposal]:
    """Run all recommenders against the clinical note and return proposals.

    ``dispense_engine_enabled`` gates only the prescription dispense-field engine
    (quantity / days supply / refills / dispense type); when False, prescribe
    recommendations are emitted in the baseline (canvas-scribe) shape. All other
    recommendation types are unaffected.
    """
    proposals: list[CommandProposal] = []
    for recommender in _build_recommenders(zip_codes, dispense_engine_enabled):
        try:
            client = LlmAnthropic(_make_settings(api_key))
            proposals.extend(recommender.recommend(note, client, transcript=transcript))
        except Exception:
            log.exception(f"Recommender {type(recommender).__name__} failed")
    return proposals
