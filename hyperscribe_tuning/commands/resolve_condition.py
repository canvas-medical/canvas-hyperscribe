from hyperscribe.handlers.constants import Constants
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class ResolveCondition(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_RESOLVE_CONDITION

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        narrative = data.get("narrative")
        if condition := data.get("condition", {}).get("text"):
            return CodedItem(label=f'{condition}: {narrative}', code="", uuid="")
        return None
