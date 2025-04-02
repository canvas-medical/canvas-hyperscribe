from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class Goal(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_GOAL

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if goal := data.get("goal_statement"):
            return CodedItem(label=goal, code="", uuid="")
        return None
