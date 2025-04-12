from hyperscribe_tuning.handlers.constants import Constants
from hyperscribe_tuning.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class ReviewOfSystem(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_REVIEW_OF_SYSTEM

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        return None
