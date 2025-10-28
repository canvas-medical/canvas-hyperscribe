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
    def note_section(cls) -> str:
        return Constants.NOTE_SECTION_PLAN

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
        return {
            "medication": "",
            "medicationIndex": -1,
            "rationale": "",
        }

    def command_parameters_schemas(self) -> list[dict]:
        medications = [medication.label for medication in self.cache.current_medications()]
        return [
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "array",
                "minItems": 1,
                "maxItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "medication": {
                            "type": "string",
                            "description": "The medication to stop",
                            "enum": medications,
                        },
                        "medicationIndex": {
                            "type": "integer",
                            "description": "Index of the medication to stop",
                            "minimum": 0,
                            "maximum": len(medications) - 1,
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Explanation of why the medication is stopped, as free text",
                        },
                    },
                    "required": ["medication", "medicationIndex", "rationale"],
                    "additionalProperties": False,
                },
            }
        ]

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
