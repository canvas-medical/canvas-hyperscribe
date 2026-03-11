from __future__ import annotations

from pydantic import Field

from canvas_sdk.clients.llms.structures import BaseModelLlmJson


class MedicationRecommendation(BaseModelLlmJson):
    medication_name: str = Field(description="Full medication name including strength")
    sig: str = Field(description="Directions/sig for the medication")
    keywords: str = Field(description="Comma-separated synonyms for searching (max 5)")


class MedicationRecommendationList(BaseModelLlmJson):
    medications: list[MedicationRecommendation] = Field(
        default_factory=list,
        description="List of medications extracted from the clinical note",
    )


class AllergyRecommendation(BaseModelLlmJson):
    allergen: str = Field(description="Name of the allergen")
    reaction: str = Field(description="Description of the allergic reaction")
    severity: str | None = Field(default=None, description="mild, moderate, or severe")
    keywords: str = Field(description="Comma-separated synonyms for searching (max 5)")


class AllergyRecommendationList(BaseModelLlmJson):
    allergies: list[AllergyRecommendation] = Field(
        default_factory=list,
        description="List of allergies extracted from the clinical note",
    )
