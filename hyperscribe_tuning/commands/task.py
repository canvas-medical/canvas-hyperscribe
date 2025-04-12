from hyperscribe_tuning.handlers.constants import Constants
from hyperscribe_tuning.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class Task(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_TASK

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        comment = data.get("comment") or "n/a"
        due_date = data.get("due_date") or "n/a"
        if task := data.get("title"):
            labels = "/".join([
                label
                for item in data.get("labels") or []
                if (label := item.get("text"))
            ]) or "n/a"
            return CodedItem(label=f"{task}: {comment} (due on: {due_date}, labels: {labels})", code="", uuid="")
        return None
