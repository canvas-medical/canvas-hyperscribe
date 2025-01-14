from canvas_sdk.commands.commands.assess import AssessCommand
from canvas_sdk.commands.commands.stop_medication import StopMedicationCommand

from commander.protocols.structures.commands.base import Base


class StopMedication(Base):

    def from_json(self, parameters: dict) -> None | AssessCommand:
        medication_id = ""
        if 0 <= (idx := parameters["medicationIndex"]) < len(self.current_medications()):
            medication_id = self.current_medications()[idx].uuid
        return StopMedicationCommand(
            medication_id=medication_id,
            rationale=parameters["rationale"],
            note_uuid=self.note_uuid,
        )

    def parameters(self) -> dict:
        medications = "/".join([f'{medication.label} (index: {idx})' for idx, medication in enumerate(self.current_medications())])
        return {
            "medication": medications,
            "medicationIndex": "Index of the medication to stop as integer",
            "rationale": "free text to explain why the medication is stopped",
        }

    def information(self) -> str:
        return ("Stop a medication. "
                "There can be only one medication, with the rationale, to stop per instruction, and no instruction in the lack of.")

    def constraints(self) -> str:
        if self.current_medications():
            text = ", ".join([medication.label for medication in self.current_medications()])
            return f"'StopMedication' has to be related to one of the following medications: {text}."
        return ""

    def is_available(self) -> bool:
        # TODO wait for https://github.com/canvas-medical/canvas-plugins/issues/321
        #  return bool(self.current_medications())
        return False
