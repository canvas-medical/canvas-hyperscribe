from pydantic import Field

from canvas_sdk.clients.llms.structures import BaseModelLlmJson


class MedicationRecommendation(BaseModelLlmJson):
    medication_name: str = Field(description="Full medication name including strength")
    sig: str | None = Field(
        default=None,
        description="Directions/sig exactly as stated in the note; leave null if no directions are stated",
    )
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
    sig: str | None = Field(
        default=None,
        description="Directions/sig exactly as stated in the note; leave null if no directions are stated",
    )
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
    indication: str | None = Field(
        default=None,
        description=(
            "The condition or problem this referral addresses, copied verbatim from the note's "
            "problem/assessment name (e.g. 'Shoulder muscle spasm'); null if the note does not state one"
        ),
    )
    clinical_question: str | None = Field(
        default=None,
        description=(
            "One of: 'Cognitive Assistance (Advice/Guidance)', "
            "'Assistance with Ongoing Management', "
            "'Specialized intervention', "
            "'Diagnostic Uncertainty'"
        ),
    )
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


class EvidenceTurn(BaseModelLlmJson):
    speaker: str = Field(description="Speaker label of the transcript turn")
    quote: str = Field(description="Verbatim quote from the transcript, lightly cleaned of disfluencies")
    item_id: str = Field(description="item_id of the transcript turn the quote came from")


class QuestionnaireItemFill(BaseModelLlmJson):
    question_dbid: int = Field(description="dbid of the question being answered")
    status: str = Field(description="answered, denied, or not_assessed")
    selected_option_dbid: int | None = Field(
        default=None, description="Single choice: dbid of the one chosen option; null otherwise"
    )
    selected_option_dbids: list[int] = Field(
        default_factory=list, description="Multiple choice: dbids of every option the respondent affirmed"
    )
    value: str | None = Field(
        default=None, description="Free-text span, or the stated integer as a string; null otherwise"
    )
    evidence: list[EvidenceTurn] = Field(
        default_factory=list, description="Transcript turn(s) supporting the answer; required unless not_assessed"
    )
    confidence: str = Field(default="low", description="high, medium, or low")
    rationale: str = Field(default="", description="One sentence linking the evidence to the classification")


class QuestionnaireFillResult(BaseModelLlmJson):
    questionnaire_dbid: int = Field(description="dbid of the questionnaire being completed")
    items: list[QuestionnaireItemFill] = Field(
        default_factory=list,
        description="One entry per answered or explicitly denied question; omit untouched questions",
    )
