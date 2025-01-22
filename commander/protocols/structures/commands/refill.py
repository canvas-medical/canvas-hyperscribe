from canvas_sdk.commands.commands.prescribe import PrescribeCommand
from canvas_sdk.commands.commands.refill import RefillCommand
from canvas_sdk.commands.constants import ClinicalQuantity
from canvas_sdk.v1.data import Medication

from commander.protocols.structures.commands.base import Base


class Refill(Base):
    def command_from_json(self, parameters: dict) -> None | RefillCommand:
        result: None | RefillCommand = None
        if 0 <= (idx := parameters["medicationIndex"]) < len(self.current_medications()):
            medication_uuid = self.current_medications()[idx].uuid
            medication = Medication.objects.get(id=medication_uuid)
            coding = medication.codings.filter(system="http://www.fdbhealth.com/").first()

            result = RefillCommand(
                fdb_code=coding.code,
                sig=parameters["sig"],
                days_supply=parameters["suppliedDays"],
                type_to_dispense=ClinicalQuantity(
                    representative_ndc=medication.national_drug_code,
                    ncpdp_quantity_qualifier_code=medication.potency_unit_code,
                ),
                substitutions=self.enum_or_none(parameters["substitution"], PrescribeCommand.Substitutions),
                prescriber_id=self.provider_uuid,
                note_uuid=self.note_uuid,
            )

        return result

    def command_parameters(self) -> dict:
        substitutions = "/".join([status.value for status in PrescribeCommand.Substitutions])
        medications = "/".join([f'{medication.label} (index: {idx})' for idx, medication in enumerate(self.current_medications())])
        return {
            "medication": f"one of: {medications}",
            "medicationIndex": "index of the medication to refill, as integer",
            "sig": "directions, as free text",
            "suppliedDays": "duration of the treatment in days, as integer",
            "substitution": f"one of: {substitutions}",
            "comment": "rational of the prescription, as free text",
        }

    def instruction_description(self) -> str:
        text = ", ".join([f'{medication.label}' for medication in self.current_medications()])
        return (f"Refill of a current medication ({text}), including the directions, the duration, the targeted condition and the dosage. "
                "There can be only one refill per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        text = ", ".join([f'{medication.label} (RxNorm: {medication.code})' for medication in self.current_medications()])
        return f"'{self.class_name()}' has to be related to one of the following medications: {text}"

    def is_available(self) -> bool:
        return bool(self.current_medications())
