from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.handlers.constants import Constants
from hyperscribe_tuning.structures.coded_item import CodedItem


class Assess(Base):

    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_ASSESS

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if (narrative := data.get("narrative")) and (condition := data.get("condition", {}).get("text")):
            return CodedItem(label=f'{condition}: {narrative}', code="", uuid="")
        return None
