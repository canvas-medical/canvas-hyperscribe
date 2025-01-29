from canvas_sdk.commands.commands.questionnaire import QuestionnaireCommand

from commander.protocols.structures.commands.base import Base


class Questionnaire(Base):
    @classmethod
    def schema_key(cls) -> str:
        return "questionnaire"

    def command_from_json(self, parameters: dict) -> None | QuestionnaireCommand:
        questionnaire_uuid = ""
        if 0 <= (idx := parameters["questionnaireIndex"]) < len(self.existing_questionnaires()):
            questionnaire_uuid = self.existing_questionnaires()[idx].uuid

        return QuestionnaireCommand(
            questionnaire_id=questionnaire_uuid,
            result=parameters["result"],
            note_uuid=self.note_uuid,
        )

    def command_parameters(self) -> dict:
        questionnaires = "/".join([f'{questionnaire.label} (index: {idx})' for idx, questionnaire in enumerate(self.existing_questionnaires())])
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
        text = ", ".join([f'"{questionnaire.label}"' for questionnaire in self.existing_questionnaires()])
        return f'"{self.class_name()}" has to be related to one of the following questionnaires: {text}'

    def is_available(self) -> bool:
        return bool(self.existing_questionnaires())
