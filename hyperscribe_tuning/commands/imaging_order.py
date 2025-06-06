from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.handlers.constants import Constants
from hyperscribe_tuning.structures.coded_item import CodedItem


class ImagingOrder(Base):

    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_IMAGING_ORDER

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        comment = data.get("comment") or "n/a"
        priority = data.get("priority") or "n/a"
        imaging = (data.get("image") or {}).get("text")
        indications = "/".join([
            indication
            for item in (data.get("indications") or [])
            if (indication := item.get("text"))
        ]) or "n/a"
        if imaging:
            return CodedItem(label=f"{imaging}: {comment} (priority: {priority}, related conditions: {indications})", code="", uuid="")
        return None
