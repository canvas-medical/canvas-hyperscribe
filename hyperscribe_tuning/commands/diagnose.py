from hyperscribe.handlers.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class Diagnose(Base):
    @classmethod
    def schema_key(cls) -> str:
        return "diagnose"

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        assessment = data.get("today_assessment") or "n/a"
        diagnose = data.get("diagnose") or {}
        if (label := diagnose.get("text")) and (code := diagnose.get("value")):
            return CodedItem(label=f"{label} ({assessment})", code=code, uuid="")
        return None
