from canvas_sdk.commands.commands.stop_medication import StopMedicationCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


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

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        result = StopMedicationCommand(
            rationale=instruction.parameters["rationale"],
            note_uuid=self.identification.note_uuid,
        )
        if 0 <= (idx := instruction.parameters["medicationIndex"]) < len(current := self.cache.current_medications()):
            result.medication_id = current[idx].uuid
            self.add_code2description(current[idx].uuid, current[idx].label)

        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        medications = "/".join(
            [f"{medication.label} (index: {idx})" for idx, medication in enumerate(self.cache.current_medications())],
        )
        return {
            "medication": f"one of: {medications}",
            "medicationIndex": "index of the medication to stop, or -1, as integer",
            "rationale": "explanation of why the medication is stopped, as free text",
        }

    def instruction_description(self) -> str:
        return (
            "Stop a medication. "
            "There can be only one medication, with the rationale, to stop per instruction, "
            "and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        text = ", ".join([medication.label for medication in self.cache.current_medications()])
        return f"'{self.class_name()}' has to be related to one of the following medications: {text}."

    def is_available(self) -> bool:
        return bool(self.cache.current_medications())
