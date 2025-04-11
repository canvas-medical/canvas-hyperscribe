from hyperscribe.handlers.constants import Constants
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class Medication(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_MEDICATION

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        sig = data.get("sig") or "n/a"
        if text := (data.get("medication") or {}).get("text"):
            return CodedItem(label=f"{text}: {sig}", code="", uuid="")
        return None
