from canvas_sdk.commands.commands.prescribe import PrescribeCommand
from canvas_sdk.commands.commands.refill import RefillCommand
from canvas_sdk.commands.constants import ClinicalQuantity, CodeSystems
from canvas_sdk.v1.data import Medication

from hyperscribe.handlers.commands.base import Base
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.helper import Helper
from hyperscribe.handlers.structures.coded_item import CodedItem


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
                      f"refills: {refills}, substitution: {substitution}, indications: {indications})",
                code="",
                uuid="",
            )
        return None

    def command_from_json(self, parameters: dict) -> None | RefillCommand:
        result: None | RefillCommand = None
        if 0 <= (idx := parameters["medicationIndex"]) < len(current := self.cache.current_medications()):
            medication_uuid = current[idx].uuid
            medication = Medication.objects.get(id=medication_uuid)
            coding = medication.codings.filter(system=CodeSystems.FDB).first()

            result = RefillCommand(
                fdb_code=coding.code,
                sig=parameters["sig"],
                days_supply=parameters["suppliedDays"],
                type_to_dispense=ClinicalQuantity(
                    representative_ndc=medication.national_drug_code,
                    ncpdp_quantity_qualifier_code=medication.potency_unit_code,
                ),
                substitutions=Helper.enum_or_none(parameters["substitution"], PrescribeCommand.Substitutions),
                prescriber_id=self.provider_uuid,
                note_uuid=self.note_uuid,
            )

        return result

    def command_parameters(self) -> dict:
        substitutions = "/".join([status.value for status in PrescribeCommand.Substitutions])
        medications = "/".join([f'{medication.label} (index: {idx})' for idx, medication in enumerate(self.cache.current_medications())])
        return {
            "medication": f"one of: {medications}",
            "medicationIndex": "index of the medication to refill, as integer",
            "sig": "directions, as free text",
            "suppliedDays": "duration of the treatment in days, as integer",
            "substitution": f"one of: {substitutions}",
            "comment": "rational of the prescription, as free text",
        }

    def instruction_description(self) -> str:
        text = ", ".join([f'{medication.label}' for medication in self.cache.current_medications()])
        return (f"Refill of a current medication ({text}), including the directions, the duration, the targeted condition and the dosage. "
                "There can be only one refill per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        text = ", ".join([f'{medication.label} (RxNorm: {medication.code})' for medication in self.cache.current_medications()])
        return f"'{self.class_name()}' has to be related to one of the following medications: {text}"

    def is_available(self) -> bool:
        return bool(self.cache.current_medications())
