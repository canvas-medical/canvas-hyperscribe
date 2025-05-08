from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.handlers.constants import Constants
from hyperscribe_tuning.structures.coded_item import CodedItem


class Allergy(Base):

    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_ALLERGY

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if (allergy := data.get("allergy", {})) and "text" in allergy and "value" in allergy:
            return CodedItem(label=allergy["text"], code=str(allergy["value"]), uuid="")
        return None
