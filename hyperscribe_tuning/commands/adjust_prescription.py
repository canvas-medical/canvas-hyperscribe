from hyperscribe_tuning.handlers.constants import Constants
from hyperscribe_tuning.structures.coded_item import CodedItem
from hyperscribe_tuning.commands.base import Base


class AdjustPrescription(Base):

    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_ADJUST_PRESCRIPTION

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        new_medication = data.get('change_medication_to', {}).get('text')
        old_medication = data.get('prescribe', {}).get('text')

        if old_medication:
            code = str((data.get('prescribe') or {}).get("value") or "")
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

            text = old_medication
            if old_medication != new_medication and new_medication:
                text = f"{old_medication} to {new_medication}"

            return CodedItem(
                label=f"{text}: {sig} (dispense: {quantity_to_dispense}, supply days: {days_supply}, "
                      f"refills: {refills}, substitution: {substitution}, related conditions: {indications})",
                code=code,
                uuid="",
            )
        return None
