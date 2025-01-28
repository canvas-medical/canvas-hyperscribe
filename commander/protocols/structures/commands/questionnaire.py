from canvas_sdk.commands.commands.questionnaire import QuestionnaireCommand

from commander.protocols.structures.commands.base import Base


class Questionnaire(Base):
    @classmethod
    def schema_key(cls) -> str:
        return "questionnaire"

    def command_from_json(self, parameters: dict) -> None | QuestionnaireCommand:
        return None

    def command_parameters(self) -> dict:
        return {}

    def instruction_description(self) -> str:
        return ""

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return False
