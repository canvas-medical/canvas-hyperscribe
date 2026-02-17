from typing import Type

from canvas_sdk.commands import PhysicalExamCommand
from logger import log

from hyperscribe.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.question import Question
from hyperscribe.structures.questionnaire import Questionnaire as QuestionnaireDefinition
from hyperscribe.structures.response import Response


class PhysicalExam(BaseQuestionnaire):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_PHYSICAL_EXAM

    def include_skipped(self) -> bool:
        return True

    def skipped_field_instruction(self) -> str:
        return (
            "CRITICAL: If a question already has 'skipped' set to 'false', you MUST keep it as 'false'. "
            "Never change 'skipped' from 'false' back to 'true' or 'null'. "
            "You may only change 'skipped' from 'true' to 'false' if the question is clearly addressed "
            "in the transcript. Body systems that are already enabled must stay enabled."
        )

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

    def post_process_questionnaire(
        self,
        original: QuestionnaireDefinition,
        updated: QuestionnaireDefinition,
    ) -> QuestionnaireDefinition:
        """Prevent the LLM from clearing existing PE findings or disabling body systems."""
        original_by_id = {q.dbid: q for q in original.questions}
        fixed_questions: list[Question] = []

        for uq in updated.questions:
            oq = original_by_id.get(uq.dbid)
            if oq is None:
                fixed_questions.append(uq)
                continue

            # Never disable a PE body system — normalize None to False,
            # and never let the LLM flip an enabled system to skipped
            skipped = uq.skipped
            if oq.skipped is not True and uq.skipped is True:
                log.info(f"[PE POST-PROCESS] Preserving enabled state for question {uq.dbid} ({uq.label})")
                skipped = oq.skipped
            if skipped is None:
                skipped = False

            # Preserve non-empty text — never let the LLM clear existing findings
            fixed_responses: list[Response] = []
            for ur, og_r in zip(uq.responses, oq.responses):
                value = ur.value
                if (
                    isinstance(og_r.value, str)
                    and og_r.value.strip()
                    and (not isinstance(ur.value, str) or not ur.value.strip())
                ):
                    log.info(f"[PE POST-PROCESS] Preserving text for question {uq.dbid} ({uq.label})")
                    value = og_r.value
                fixed_responses.append(Response(dbid=ur.dbid, value=value, selected=ur.selected, comment=ur.comment))

            fixed_questions.append(
                Question(
                    dbid=uq.dbid,
                    label=uq.label,
                    type=uq.type,
                    skipped=skipped,
                    responses=fixed_responses,
                )
            )

        return QuestionnaireDefinition(dbid=updated.dbid, name=updated.name, questions=fixed_questions)

    def sdk_command(self) -> Type[PhysicalExamCommand]:
        return PhysicalExamCommand  # type: ignore
