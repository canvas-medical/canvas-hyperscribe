from hyperscribe.handlers.constants import Constants
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class StopMedication(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_STOP_MEDICATION

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        rationale = data.get("rationale") or "n/a"
        if medication := (data.get("medication") or {}).get("text"):
            return CodedItem(label=f"{medication}: {rationale}", code="", uuid="")
        return None
