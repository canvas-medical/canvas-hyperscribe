from canvas_sdk.commands.commands.assess import AssessCommand
from canvas_sdk.commands.commands.stop_medication import StopMedicationCommand

from commander.protocols.structures.commands.base import Base


class StopMedication(Base):

    def from_json(self, parameters: dict) -> None | AssessCommand:
        medication_id = ""
        if 0 <= (idx := parameters["medicationIndex"]) < len(self.current_medications()):
            medication_id = (self.current_medications()[idx]["uuid"])
        return StopMedicationCommand(
            medication_id=medication_id,
            rationale=parameters["rationale"],
            note_uuid=self.note_uuid,
        )

    def parameters(self) -> dict:
        medications = "/".join([f'{medication["label"]} (index: {idx})' for idx, medication in enumerate(self.current_medications())])
        return {
            "medication": medications,
            "medicationIndex": "Index of the medication to stop as integer",
            "rationale": "free text to explain why the medication is stopped",
        }

    def information(self) -> str:
        text = [
            f'* {medication["label"]} (RxNorm: {medication["code"]})'
            for medication in self.current_medications()
        ]
        text.insert(0, "Stop a medication, limited to:")
        text.append("There can be only one medication, with the rationale, to stop per instruction, and no instruction in the lack of.")
        return "\n".join(text)

    def is_available(self) -> bool:
        return bool(self.current_medications())
