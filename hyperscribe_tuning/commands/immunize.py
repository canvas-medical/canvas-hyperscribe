from hyperscribe_tuning.handlers.constants import Constants
from hyperscribe_tuning.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class Immunize(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_IMMUNIZE

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        manufacturer = data.get("manufacturer") or "n/a"
        sig_original = data.get("sig_original") or "n/a"
        if immunization := (data.get("coding") or {}).get("text"):
            return CodedItem(label=f"{immunization}: {sig_original} ({manufacturer})", code="", uuid="")
        return None
