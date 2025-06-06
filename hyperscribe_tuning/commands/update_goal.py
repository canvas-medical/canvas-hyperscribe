from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.handlers.constants import Constants
from hyperscribe_tuning.structures.coded_item import CodedItem


class UpdateGoal(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_UPDATE_GOAL

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if (progress := data.get("progress")) and (goal := data.get("goal_statement", {}).get("text")):
            return CodedItem(label=f'{goal}: {progress}', code="", uuid="")
        return None
