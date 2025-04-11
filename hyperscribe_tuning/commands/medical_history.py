from hyperscribe.handlers.constants import Constants
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class MedicalHistory(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_MEDICAL_HISTORY

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        comment = data.get("comments") or "n/a"
        start_date = (data.get("approximate_start_date") or {}).get("date") or "n/a"
        end_date = (data.get("approximate_end_date") or {}).get("date") or "n/a"
        if text := (data.get("past_medical_history") or {}).get("text"):
            return CodedItem(label=f"{text}: from {start_date} to {end_date} ({comment})", code="", uuid="")
        return None
