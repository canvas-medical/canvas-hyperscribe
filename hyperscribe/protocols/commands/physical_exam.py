from canvas_sdk.commands.commands.exam import PhysicalExamCommand

from hyperscribe.protocols.commands.base import Base
from hyperscribe.protocols.constants import Constants
from hyperscribe.protocols.structures.coded_item import CodedItem


class PhysicalExam(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_PHYSICAL_EXAM

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if text := (data.get("questionnaire") or {}).get("text"):
            questions = " \n ".join([
                data.get(name)
                for question in (data.get("questionnaire") or {}).get("extra", {}).get("questions", [])
                if (name := question.get("name")) and data.get(name)
            ])
            return CodedItem(label=f"{text}: {questions}", code="", uuid="")
        return None

    def command_from_json(self, parameters: dict) -> None | PhysicalExamCommand:
        return None

    def command_parameters(self) -> dict:
        return {}

    def instruction_description(self) -> str:
        return ""

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return False
