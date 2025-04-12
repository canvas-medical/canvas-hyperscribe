from hyperscribe_tuning.handlers.constants import Constants
from hyperscribe_tuning.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class FollowUp(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_FOLLOW_UP

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        encounter = (data.get("note_type") or {}).get("text") or "n/a"
        on_date = (data.get("requested_date") or {}).get("date")
        reason_for_visit = data.get("reason_for_visit")
        if text := (data.get("coding") or {}).get("text"):
            reason_for_visit = text

        if on_date and reason_for_visit:
            return CodedItem(label=f"{on_date}: {reason_for_visit} ({encounter})", code="", uuid="")
        return None
