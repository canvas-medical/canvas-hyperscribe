from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class ReasonForVisit(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_REASON_FOR_VISIT

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        reason_for_visit = data.get("comment")
        if text := (data.get("coding") or {}).get("text"):
            reason_for_visit = text
        if reason_for_visit:
            return CodedItem(label=reason_for_visit, code="", uuid="")
        return None
