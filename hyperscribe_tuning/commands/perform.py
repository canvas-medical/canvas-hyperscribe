from hyperscribe.handlers.constants import Constants
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class Perform(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_PERFORM

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        notes = data.get("notes") or "n/a"
        if text := (data.get("perform") or {}).get("text"):
            return CodedItem(label=f"{text}: {notes}", code="", uuid="")
        return None
