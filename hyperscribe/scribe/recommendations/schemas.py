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


class PrescriptionRecommendation(BaseModelLlmJson):
    medication_name: str = Field(description="Full medication name including strength/form")
    sig: str = Field(description="Directions/sig for the prescription")
    days_supply: int | None = Field(default=None, description="Number of days supply")
    quantity_to_dispense: str | None = Field(default=None, description="Quantity to dispense")
    refills: int | None = Field(default=None, description="Number of refills")
    keywords: str = Field(description="Comma-separated synonyms for searching (max 5)")


class PrescriptionRecommendationList(BaseModelLlmJson):
    prescriptions: list[PrescriptionRecommendation] = Field(
        default_factory=list,
        description="List of new prescriptions to be written",
    )


class ReferRecommendation(BaseModelLlmJson):
    specialty: str = Field(description="Medical specialty for the referral (e.g. Cardiology, ENT, Dermatology)")
    clinical_question: str | None = Field(
        default=None,
        description=(
            "One of: 'Cognitive Assistance (Advice/Guidance)', "
            "'Assistance with Ongoing Management', "
            "'Specialized intervention', "
            "'Diagnostic Uncertainty'"
        ),
    )
    priority: str = Field(default="Routine", description="'Routine' or 'Urgent'")
    reason: str | None = Field(default=None, description="Brief reason or notes for the referral")


class ReferRecommendationList(BaseModelLlmJson):
    referrals: list[ReferRecommendation] = Field(
        default_factory=list,
        description="List of referrals extracted from the clinical note",
    )


class ReconciliationSection(BaseModelLlmJson):
    key: str = Field(description="Lowercase key for the system (e.g. 'constitutional', 'eyes')")
    title: str = Field(description="Display title (e.g. 'CONSTITUTIONAL', 'EYES')")
    text: str = Field(description="The final clinical text for this system")
    updated: bool = Field(
        description=(
            "true if the text was changed from the template based on encounter findings, "
            "false if the template text was kept exactly as-is"
        ),
    )


class ReconciliationResult(BaseModelLlmJson):
    sections: list[ReconciliationSection] = Field(
        default_factory=list,
        description="Reconciled sections with update attribution",
    )


class TaskRecommendation(BaseModelLlmJson):
    title: str = Field(description="Concise task title (e.g. 'Schedule follow-up in 2 weeks')")
    due_date_hint: str | None = Field(
        default=None,
        description="Relative or absolute due date if mentioned (e.g. '2 weeks', 'next Monday')",
    )
    assignee_hint: str | None = Field(
        default=None,
        description="Who should handle this task if mentioned (e.g. 'front desk', 'nurse')",
    )
    comment: str | None = Field(default=None, description="Additional details or context for the task")
    reason: str = Field(
        description="The transcript excerpt or context that prompted this task recommendation",
    )


class TaskRecommendationList(BaseModelLlmJson):
    tasks: list[TaskRecommendation] = Field(
        default_factory=list,
        description="List of tasks extracted from the transcript and clinical note",
    )


class DiagnosisSuggestion(BaseModelLlmJson):
    condition_text: str = Field(description="The original condition text")
    icd10_codes: list[str] = Field(description="2-3 ICD-10 codes (e.g. R519, G43009)")


class DiagnosisSuggestionList(BaseModelLlmJson):
    suggestions: list[DiagnosisSuggestion] = Field(
        default_factory=list,
        description="List of diagnosis suggestions per condition",
    )


class LabTestEntry(BaseModelLlmJson):
    name: str = Field(description="Display name of the test (e.g. 'Complete Blood Count')")
    keywords: str = Field(
        description="Comma-separated synonyms for compendium search (max 5)",
    )


class LabRecommendation(BaseModelLlmJson):
    tests: list[LabTestEntry] = Field(
        description="Tests intended to be ordered together as one requisition",
    )
    fasting_required: bool | None = Field(
        default=None,
        description="True if provider mentioned fasting; null if not discussed",
    )
    comment: str | None = Field(
        default=None,
        description="Brief note about the order (max 128 chars)",
    )
    reason: str = Field(
        description="Note excerpt or paraphrase explaining why the provider is ordering this",
    )


class LabRecommendationList(BaseModelLlmJson):
    orders: list[LabRecommendation] = Field(
        default_factory=list,
        description="List of lab orders extracted from the clinical note",
    )


class AoeAnswer(BaseModelLlmJson):
    test_order_code: str = Field(description="The order_code of the test this answer is for")
    question_code: str = Field(description="The AOE question code")
    answer: str = Field(
        description=(
            "Answer value. For select/radio: the matching choice's `value`. "
            "For text: short faithful free text. For date: ISO date. "
            "For boolean/numeric: the literal value."
        ),
    )
    confidence: str = Field(
        description=("'high' if directly stated in transcript, 'medium' if clearly inferable, 'low' if guessed"),
    )


class AoeAnswerList(BaseModelLlmJson):
    answers: list[AoeAnswer] = Field(
        default_factory=list,
        description="List of AOE answers extracted from the transcript",
    )
