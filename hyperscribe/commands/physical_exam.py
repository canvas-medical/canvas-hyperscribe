from typing import Type

from canvas_sdk.commands import PhysicalExamCommand

from hyperscribe.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe.libraries.constants import Constants


class PhysicalExam(BaseQuestionnaire):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_PHYSICAL_EXAM

    def include_skipped(self) -> bool:
        return True

    def additional_instructions(self) -> list[str]:
        return [
            "The questionnaire pertains to a physical examination. Only include objective findings "
            "from the provider's physical examination of the patient. This includes observations, "
            'measurements, and results of maneuvers performed by the provider (e.g., "pupils equal, '
            'round, and reactive to light", "abdomen soft, non-tender", "CN II\u2013XII grossly '
            'intact"). Do not include patient-reported symptoms, subjective complaints, diagnoses, '
            "assessments, or treatment plans \u2014 these belong in other sections of the clinical note.",
            "If the transcript does not contain any physical exam findings, do not modify the questionnaire values.",
        ]

    def sdk_command(self) -> Type[PhysicalExamCommand]:
        return PhysicalExamCommand  # type: ignore
