from canvas_sdk.commands.commands.prescribe import PrescribeCommand

from commander.protocols.structures.commands.base import Base


class Prescription(Base):
    def from_json(self, parameters: dict) -> None | PrescribeCommand:
        count_conditions = len(self.current_conditions())
        condition_ids = [
            (self.current_conditions()[idx]["uuid"])
            for idx in parameters["conditionIndexes"] if 0 <= idx < count_conditions
        ]

        return PrescribeCommand(
            fdb_code=None,  # TODO retrieve the FDB code
            icd10_codes=condition_ids,
            sig=f'{parameters["sig"]} - {parameters["medication"]}',
            days_supply=parameters["suppliedDays"],
            quantity_to_dispense=parameters["quantityToDispense"],
            refills=parameters["refills"],
            substitutions=PrescribeCommand.Substitutions(parameters["substitution"]),
            note_to_pharmacist=parameters["noteToPharmacist"],
            note_uuid=self.note_uuid,
        )

    def parameters(self) -> dict:
        substitutions = "/".join([status.value for status in PrescribeCommand.Substitutions])
        conditions = "/".join([f'{condition["label"]} (index: {idx})' for idx, condition in enumerate(self.current_conditions())])
        return {
            "medication": "name of the prescribed medication",
            "condition": conditions,
            "conditionIndexes": ["Indexes of the Condition for which the medication is prescribed, as integers"],
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
