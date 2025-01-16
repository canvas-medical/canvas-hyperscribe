from canvas_sdk.commands.commands.assess import AssessCommand
from canvas_sdk.commands.commands.stop_medication import StopMedicationCommand

from commander.protocols.structures.commands.base import Base


class StopMedication(Base):

    def command_from_json(self, parameters: dict) -> None | AssessCommand:
        medication_uuid = ""
        if 0 <= (idx := parameters["medicationIndex"]) < len(self.current_medications()):
            medication_uuid = self.current_medications()[idx].uuid
        return StopMedicationCommand(
            medication_id=medication_uuid,
            rationale=parameters["rationale"],
            note_uuid=self.note_uuid,
        )

    def command_parameters(self) -> dict:
        medications = "/".join([f'{medication.label} (index: {idx})' for idx, medication in enumerate(self.current_medications())])
        return {
            "medication": f"one of: {medications}",
            "medicationIndex": "index of the medication to stop, as integer",
            "rationale": "explanation of why the medication is stopped, as free text",
        }

    def instruction_description(self) -> str:
        return ("Stop a medication. "
                "There can be only one medication, with the rationale, to stop per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        result = ""
        if self.current_medications():
            text = ", ".join([medication.label for medication in self.current_medications()])
            result = f"'{self.class_name()}' has to be related to one of the following medications: {text}."
        return result

    def is_available(self) -> bool:
        # TODO wait for https://github.com/canvas-medical/canvas-plugins/issues/321
        #  return bool(self.current_medications())
        return False
