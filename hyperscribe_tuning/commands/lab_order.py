from hyperscribe_tuning.handlers.constants import Constants
from hyperscribe_tuning.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class LabOrder(Base):

    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_LAB_ORDER

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        fasting = "n/a"
        if "fasting_status" in data:
            fasting = "yes" if data["fasting_status"] is True else "no"
        diagnosis = "/".join([
            diagnose
            for item in (data.get("diagnosis") or [])
            if (diagnose := item.get("text"))
        ]) or "n/a"
        comment = data.get("comment") or "n/a"
        tests = "/".join([
            test
            for item in (data.get("tests") or [])
            if (test := item.get("text"))
        ])

        if tests:
            return CodedItem(label=f"{tests}: {comment} (fasting: {fasting}, diagnosis: {diagnosis})", code="", uuid="")
        return None
