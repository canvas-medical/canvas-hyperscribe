from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.handlers.constants import Constants
from hyperscribe_tuning.structures.coded_item import CodedItem


class FamilyHistory(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_FAMILY_HISTORY

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        label = (data.get("family_history") or {}).get("text")
        relative = (data.get("relative") or {}).get("text")
        if label and relative:
            return CodedItem(label=f"{relative}: {label}", code="", uuid="")
        return None
