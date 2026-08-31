from __future__ import annotations

import re

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


def make_llm_client(api_key: str) -> LlmAnthropic:
    """Public factory for an Anthropic client with the recommendations settings.

    Lets callers outside this module (e.g. the diagnosis LLM resolver wired into
    ``session_view``) build a client without reaching into ``_make_settings``.
    """
    return LlmAnthropic(_make_settings(api_key))


def _staffer_allowed(allowlist_raw: str | None, provider_id: str | None) -> bool:
    """Shared allowlist check for the scribe staffer secrets.

    The allowlist is a comma/space-separated list of staff keys. **Blank/unset ->
    enabled for all users** (fail-open, by product decision); otherwise enabled only
    when the note's provider is in the list.
    """
    allowed = re.findall(r"[A-Za-z0-9]+", allowlist_raw or "")
    if not allowed:
        return True
    return bool(provider_id) and str(provider_id) in allowed


def prescription_dispense_enabled(allowlist_raw: str | None, provider_id: str | None) -> bool:
    """Whether the prescription dispense-field engine is enabled for this provider."""
    return _staffer_allowed(allowlist_raw, provider_id)


def questionnaire_fill_enabled(allowlist_raw: str | None, provider_id: str | None) -> bool:
    """Whether filling questionnaires from the transcript is enabled for this provider."""
    return _staffer_allowed(allowlist_raw, provider_id)


_TRUTHY = {"yes", "y", "1", "true", "on"}


def lab_aoe_enabled(raw: str | None) -> bool:
    """Whether the lab Ask-On-Order-Entry pass is turned on.

    **Blank/unset -> off** (fail-closed), the opposite of
    ``prescription_dispense_enabled``: the AOE answers are review-only today, since
    ``LabOrderCommand`` has no field to persist them to.

    Accepts every truthy spelling the repo already uses, because ``Settings.is_true``
    takes yes/y/1 while ``scribe_view`` takes only "true", and a secret set with the
    other convention would silently do nothing.
    """
    return str(raw or "").strip().lower() in _TRUTHY


def _build_recommenders(
    zip_codes: list[str] | None = None,
    dispense_engine_enabled: bool = True,
    aoe_enabled: bool = False,
) -> list[BaseRecommender]:
    return [
        MedicationRecommender(),
        AllergyRecommender(),
        PrescriptionRecommender(dispense_engine_enabled=dispense_engine_enabled),
        # zip_codes is intentionally not passed: referrals are recommended
        # generically (specialty only), without a provider lookup.
        ReferRecommender(),
        LabRecommender(aoe_enabled=aoe_enabled),
        TaskRecommender(),
    ]


def recommend_commands(
    note: ClinicalNote,
    api_key: str,
    zip_codes: list[str] | None = None,
    transcript: Transcript | None = None,
    dispense_engine_enabled: bool = True,
    aoe_enabled: bool = False,
) -> list[CommandProposal]:
    """Run all recommenders against the clinical note and return proposals.

    ``dispense_engine_enabled`` gates only the prescription dispense-field engine
    (quantity / days supply / refills / dispense type); when False, prescribe
    recommendations are emitted in the baseline (canvas-scribe) shape. All other
    recommendation types are unaffected.

    ``aoe_enabled`` gates only the lab Ask-On-Order-Entry pass and defaults to off.
    """
    proposals: list[CommandProposal] = []
    for recommender in _build_recommenders(zip_codes, dispense_engine_enabled, aoe_enabled):
        try:
            client = LlmAnthropic(_make_settings(api_key))
            proposals.extend(recommender.recommend(note, client, transcript=transcript))
        except Exception:
            log.exception(f"Recommender {recommender.__class__.__name__} failed")
    return proposals
