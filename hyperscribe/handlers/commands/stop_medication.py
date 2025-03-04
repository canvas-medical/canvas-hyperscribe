from canvas_sdk.commands.commands.stop_medication import StopMedicationCommand

from hyperscribe.handlers.commands.base import Base
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.structures.coded_item import CodedItem


class StopMedication(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_STOP_MEDICATION

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        rationale = data.get("rationale") or "n/a"
        if medication := (data.get("medication") or {}).get("text"):
            return CodedItem(label=f"{medication}: {rationale}", code="", uuid="")
        return None

    def command_from_json(self, parameters: dict) -> None | StopMedicationCommand:
        medication_uuid = ""
        if 0 <= (idx := parameters["medicationIndex"]) < len(current := self.cache.current_medications()):
            medication_uuid = current[idx].uuid
        return StopMedicationCommand(
            medication_id=medication_uuid,
            rationale=parameters["rationale"],
            note_uuid=self.note_uuid,
        )

    def command_parameters(self) -> dict:
        medications = "/".join([f'{medication.label} (index: {idx})' for idx, medication in enumerate(self.cache.current_medications())])
        return {
            "medication": f"one of: {medications}",
            "medicationIndex": "index of the medication to stop, as integer",
            "rationale": "explanation of why the medication is stopped, as free text",
        }

    def instruction_description(self) -> str:
        return ("Stop a medication. "
                "There can be only one medication, with the rationale, to stop per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        text = ", ".join([medication.label for medication in self.cache.current_medications()])
        return f"'{self.class_name()}' has to be related to one of the following medications: {text}."

    def is_available(self) -> bool:
        # TODO wait for https://github.com/canvas-medical/canvas-plugins/issues/321
        #  return bool(self.cache.current_medications())
        return False
