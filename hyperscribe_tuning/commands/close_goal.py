from hyperscribe.handlers.constants import Constants
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class CloseGoal(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_CLOSE_GOAL

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if text := (data.get("goal_id") or {}).get("text"):
            return CodedItem(label=f'{text} ({data.get("progress") or "n/a"})', code="", uuid="")
        return None
