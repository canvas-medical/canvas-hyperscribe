from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.handlers.constants import Constants
from hyperscribe_tuning.structures.coded_item import CodedItem


class SurgeryHistory(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_SURGERY_HISTORY

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        comment = data.get("comment") or "n/a"
        on_date = (data.get("approximate_date") or {}).get("date") or "n/a"
        if surgery := (data.get("past_surgical_history") or {}).get("text"):
            code = str((data.get('past_surgical_history') or {}).get("value") or "")
            return CodedItem(label=f"{surgery}: {comment} (on: {on_date})", code=code, uuid="")
        return None
