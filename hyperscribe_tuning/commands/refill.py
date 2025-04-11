from hyperscribe.handlers.constants import Constants
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class Refill(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_REFILL

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if (prescribe := data.get("prescribe")) and (text := prescribe.get("text")):
            sig = data.get('sig') or "n/a"
            refills = data.get('refills') or "n/a"
            quantity_to_dispense = data.get('quantity_to_dispense') or "n/a"
            days_supply = data.get('days_supply') or "n/a"
            substitution = data.get('substitutions') or "n/a"
            indications = "/".join([
                indication
                for question in (data.get("indications") or [])
                if (indication := question.get("text"))
            ]) or "n/a"
            return CodedItem(
                label=f"{text}: {sig} (dispense: {quantity_to_dispense}, supply days: {days_supply}, "
                      f"refills: {refills}, substitution: {substitution}, related conditions: {indications})",
                code="",
                uuid="",
            )
        return None
