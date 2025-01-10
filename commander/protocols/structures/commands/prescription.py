from canvas_sdk.commands.commands.prescribe import PrescribeCommand

from commander.protocols.structures.commands.base import Base


class Prescription(Base):
    def from_json(self, parameters: dict) -> PrescribeCommand:
        return PrescribeCommand(
            fdb_code=None,  # TODO retrieve the FDB code
            icd10_codes=[],
            sig=f'{parameters["sig"]} - {parameters["medication"]}',
            days_supply=parameters["suppliedDays"],
            quantity_to_dispense=parameters["quantityToDispense"],
            refills=parameters["refills"],
            substitutions=parameters["substitutions"],
            note_to_pharmacist=parameters["noteToPharmacist"],
        )

    def parameters(self) -> dict:
        substitutions = "/".join([status.value for status in PrescribeCommand.Substitutions])
        return {
            "medication": "name of the prescribed medication",
            "indications": ["list of the related conditions", "one item per condition"],
            "sig": "directions as free text",
            "suppliedDays": 0,
            "quantityToDispense": 0,
            "refills": 0,
            "substitution": substitutions,
            "noteToPharmacist": "note to the pharmacist as free text",
        }

    def information(self) -> str:
        return ("Medication prescription, including the name and the dosage. "
                "There can be only one prescription per instruction, and no instruction in the lack of.")

    def is_available(self) -> bool:
        return True
