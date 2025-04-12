from hyperscribe_tuning.handlers.constants import Constants
from hyperscribe_tuning.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class RemoveAllergy(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_REMOVE_ALLERGY

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        narrative = data.get("narrative") or "n/a"
        if allergy := (data.get("allergy") or {}).get("text"):
            return CodedItem(label=f"{allergy}: {narrative}", code="", uuid="")
        return None
