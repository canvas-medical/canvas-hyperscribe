from canvas_sdk.commands.commands.review_of_systems import ReviewOfSystemsCommand

from hyperscribe.commands.base import Base
from hyperscribe.handlers.constants import Constants
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem


class ReviewOfSystem(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_REVIEW_OF_SYSTEM

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        return None

    def command_from_json(self, chatter: LlmBase, parameters: dict) -> None | ReviewOfSystemsCommand:
        return None

    def command_parameters(self) -> dict:
        return {}

    def instruction_description(self) -> str:
        return ""

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return False
