from canvas_sdk.commands.commands.questionnaire import QuestionnaireCommand

from hyperscribe.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe.handlers.constants import Constants
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class Questionnaire(BaseQuestionnaire):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_QUESTIONNAIRE

    def command_from_json(self, instruction: InstructionWithParameters, chatter: LlmBase) -> InstructionWithCommand | None:
        questionnaire_uuid = ""
        if 0 <= (idx := instruction.parameters["questionnaireIndex"]) < len(current := self.cache.existing_questionnaires()):
            questionnaire_uuid = current[idx].uuid

        return InstructionWithCommand.add_command(instruction, QuestionnaireCommand(
            questionnaire_id=questionnaire_uuid,
            result=instruction.parameters["result"],
            note_uuid=self.identification.note_uuid,
        ))

    def command_parameters(self) -> dict:
        questionnaires = "/".join([f'{questionnaire.label} (index: {idx})' for idx, questionnaire in enumerate(self.cache.existing_questionnaires())])
        return {
            "questionnaire": f"one of: {questionnaires}, mandatory",
            "questionnaireIndex": "index of the questionnaire, as integer",
            "result": "the conclusion of the clinician based on the patient's answers, as free text",
        }

    def instruction_description(self) -> str:
        return ("Questionnaire submitted by the clinician, including the questions and patient's responses. "
                "There can be only one questionnaire per instruction, and no instruction in the lack of. "
                "Each type of questionnaire can be submitted only once per discussion.")

    def instruction_constraints(self) -> str:
        text = ", ".join([f'"{questionnaire.label}"' for questionnaire in self.cache.existing_questionnaires()])
        return f'"{self.class_name()}" has to be related to one of the following questionnaires: {text}'

    def is_available(self) -> bool:
        return bool(self.cache.existing_questionnaires())
