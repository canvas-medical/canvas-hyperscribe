from canvas_sdk.commands.commands.reason_for_visit import ReasonForVisitCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class ReasonForVisit(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_REASON_FOR_VISIT

    @classmethod
    def note_section(cls) -> str:
        return Constants.SECTION_SUBJECTIVE

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        reason_for_visit = data.get("comment")
        if text := (data.get("coding") or {}).get("text"):
            reason_for_visit = text
        if reason_for_visit:
            return CodedItem(label=reason_for_visit, code="", uuid="")
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        result = ReasonForVisitCommand(
            comment=instruction.parameters["comment"],
            note_uuid=self.identification.note_uuid,
        )
        if "reasonForVisitIndex" in instruction.parameters:
            if (
                0
                <= (idx := instruction.parameters["reasonForVisitIndex"])
                < len(existing := self.cache.existing_reason_for_visits())
            ):
                result.structured = True
                result.coding = existing[idx].uuid
                self.add_code2description(existing[idx].uuid, existing[idx].label)

        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        result: dict = {"comment": ""}
        if self.settings.structured_rfv:
            result |= {
                "reasonForVisit": "",
                "reasonForVisitIndex": -1,
            }
        return result

    def command_parameters_schemas(self) -> list[dict]:
        fields = {}
        if self.settings.structured_rfv:
            fields = {
                "reasonForVisit": {
                    "type": "string",
                    "enum": [r.label for r in self.cache.existing_reason_for_visits()],
                },
                "reasonForVisitIndex": {
                    "type": "integer",
                },
            }

        return [
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "array",
                "minItems": 1,
                "maxItems": 1,
                "items": {
                    "type": "object",
                    "properties": fields
                    | {
                        "comment": {
                            "type": "string",
                            "description": "extremely concise description of the reason or "
                            "impetus for the visit, as free text",
                        },
                    },
                    "required": list(fields.keys()) + ["comment"],
                    "additionalProperties": False,
                },
            },
        ]

    def instruction_description(self) -> str:
        return (
            "Patient's stated symptom, problem or reason for the visit. "
            "If this instruction already exists, "
            "update it by adding a concise 2-5 word clinical summary of the chief complaint "
            "or main presenting issue as the first line, followed by any existing content. "
            "The summary should capture why the patient is being seen (e.g., 'Work-related "
            "stress and anxiety' or 'Lower back pain'). "
            "There can be multiple reasons within an instruction, "
            "but only one such instruction in the whole discussion. "
        )

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        if self.settings.structured_rfv:
            return bool(self.cache.existing_reason_for_visits())
        return True
