import json

from canvas_sdk.commands.commands.medication_statement import MedicationStatementCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class Medication(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_MEDICATION

    @classmethod
    def note_section(cls) -> str:
        return Constants.NOTE_SECTION_HISTORY

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        sig = data.get("sig") or "n/a"
        if text := (data.get("medication") or {}).get("text"):
            return CodedItem(label=f"{text}: {sig}", code="", uuid="")
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        result = MedicationStatementCommand(sig=instruction.parameters["sig"], note_uuid=self.identification.note_uuid)
        # retrieve existing medications defined in Canvas Science
        expressions = instruction.parameters["keywords"].split(",")
        if medications := CanvasScience.medication_details(expressions):
            # retrieve the correct medication
            system_prompt = [
                "Medical context: identify the single most relevant medication from the list.",
                "",
            ]
            user_prompt = [
                "Provider data:",
                "```text",
                f"keywords: {instruction.parameters['keywords']}",
                instruction.parameters["sig"],
                "```",
                "",
                "Medications:",
                "\n".join(
                    f" * {medication.description} (fdbCode: {medication.fdb_code})" for medication in medications
                ),
                "",
                "Return the ONE most relevant medication as JSON in Markdown code block:",
                "```json",
                json.dumps([{"fdbCode": "int", "description": "description"}]),
                "```",
                "",
            ]
            schemas = JsonSchema.get(["selector_fdb_code"])
            if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
                medication = response[0]
                result.fdb_code = str(medication["fdbCode"])
                self.add_code2description(medication["fdbCode"], medication["description"])
        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        return {
            "keywords": "",
            "sig": "",
        }

    def command_parameters_schemas(self) -> list[dict]:
        return [
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "array",
                "minItems": 1,
                "maxItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "keywords": {
                            "type": "string",
                            "description": "Up to 5 comma-separated medication synonyms",
                        },
                        "sig": {
                            "type": "string",
                            "description": "Directions",
                        },
                    },
                    "required": ["keywords", "sig"],
                    "additionalProperties": False,
                },
            }
        ]

    def instruction_description(self) -> str:
        return (
            "Current medication being consumed by the patient, not a new prescription order. "
            "There can be only one medication per instruction, and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        result = ""
        if text := ", ".join([medication.label for medication in self.cache.current_medications()]):
            result = f"Only document '{self.class_name()}' for medications outside the following list: {text}."
        return result

    def is_available(self) -> bool:
        return True
