from canvas_sdk.commands.commands.stop_medication import StopMedicationCommand

from commander.protocols.commands.base import Base


class StopMedication(Base):
    @classmethod
    def schema_key(cls) -> str:
        return "stopMedication"

    def command_from_json(self, parameters: dict) -> None | StopMedicationCommand:
        medication_uuid = ""
        if 0 <= (idx := parameters["medicationIndex"]) < len(current := self.current_medications()):
            medication_uuid = current[idx].uuid
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
        text = ", ".join([medication.label for medication in self.current_medications()])
        return f"'{self.class_name()}' has to be related to one of the following medications: {text}."

    def is_available(self) -> bool:
        # TODO wait for https://github.com/canvas-medical/canvas-plugins/issues/321
        #  return bool(self.current_medications())
        return False
