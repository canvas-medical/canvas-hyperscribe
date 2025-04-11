from hyperscribe.handlers.constants import Constants
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class HistoryOfPresentIllness(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_HISTORY_OF_PRESENT_ILLNESS

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if narrative := data.get("narrative"):
            return CodedItem(label=narrative, code="", uuid="")
        return None
