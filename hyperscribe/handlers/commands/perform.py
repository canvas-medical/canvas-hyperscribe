from canvas_sdk.commands.commands.perform import PerformCommand

from hyperscribe.handlers.commands.base import Base
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.structures.coded_item import CodedItem


class Perform(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_PERFORM

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        return None

    def command_from_json(self, parameters: dict) -> None | PerformCommand:
        return None

    def command_parameters(self) -> dict:
        return {}

    def instruction_description(self) -> str:
        return ""

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return False
