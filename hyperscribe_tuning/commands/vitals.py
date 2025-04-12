from hyperscribe_tuning.handlers.constants import Constants
from hyperscribe_tuning.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class Vitals(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_VITALS

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if text := ", ".join([f"{k}: {v}" for k, v in data.items() if v]):
            return CodedItem(label=text, code="", uuid="")
        return None
