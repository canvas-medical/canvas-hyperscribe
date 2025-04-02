from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class Plan(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_PLAN

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if text := data.get("narrative"):
            return CodedItem(label=text, code="", uuid="")
        return None
