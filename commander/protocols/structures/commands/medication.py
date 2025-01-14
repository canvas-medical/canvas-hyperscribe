from canvas_sdk.commands.commands.medication_statement import MedicationStatementCommand

from commander.protocols.structures.commands.base import Base


class Medication(Base):
    def from_json(self, parameters: dict) -> None | MedicationStatementCommand:
        return MedicationStatementCommand(
            fdb_code=None,  # TODO retrieve the FDB code
            sig=f'{parameters["sig"]} - {parameters["medication"]}',
            note_uuid=self.note_uuid,
        )

    def parameters(self) -> dict:
        return {
            "medication": "name of the taken medication",
            "sig": "directions as free text",
        }

    def information(self) -> str:
        if self.current_medications():
            text = [
                f'* {medication.label} (RxNorm: {medication.code})'
                for medication in self.current_medications()
            ]
            text.insert(0, "Current medication not included in:")
            text.append("There can be only one medication per instruction, and no instruction in the lack of.")
            return "\n".join(text)

        return ("Current medication. "
                "There can be only one medication per instruction, and no instruction in the lack of.")

    def is_available(self) -> bool:
        return True
