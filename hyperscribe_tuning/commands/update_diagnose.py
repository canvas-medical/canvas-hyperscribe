from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class UpdateDiagnose(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_UPDATE_DIAGNOSE

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if condition := (data.get("condition") or {}).get("text"):
            new_condition = (data.get("new_condition") or {}).get("text") or "n/a"
            narrative = data.get("narrative") or "n/a"
            return CodedItem(label=f"{condition} to {new_condition}: {narrative}", code="", uuid="")
        return None
