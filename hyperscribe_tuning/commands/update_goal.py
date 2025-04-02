from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class UpdateGoal(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_UPDATE_GOAL

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if (progress := data.get("progress")) and (goal := data.get("goal_statement", {}).get("text")):
            return CodedItem(label=f'{goal}: {progress}', code="", uuid="")
        return None
