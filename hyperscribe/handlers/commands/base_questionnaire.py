from hyperscribe.handlers.commands.base import Base
from hyperscribe.handlers.structures.coded_item import CodedItem


class BaseQuestionnaire(Base):

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if text := (data.get("questionnaire") or {}).get("text"):
            questions = " \n ".join([
                label
                for question in (data.get("questionnaire") or {}).get("extra", {}).get("questions", [])
                if (label := question.get("label"))
            ])
            return CodedItem(label=f"{text}: {questions}", code="", uuid="")
        return None
