from canvas_sdk.commands.commands.follow_up import FollowUpCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class FollowUp(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_FOLLOW_UP

    @classmethod
    def note_section(cls) -> str:
        return Constants.NOTE_SECTION_PLAN

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        encounter = (data.get("note_type") or {}).get("text") or "n/a"
        on_date = (data.get("requested_date") or {}).get("date")
        reason_for_visit = data.get("reason_for_visit")
        if text := (data.get("coding") or {}).get("text"):
            reason_for_visit = text

        if on_date and reason_for_visit:
            return CodedItem(label=f"{on_date}: {reason_for_visit} ({encounter})", code="", uuid="")
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        result = FollowUpCommand(
            note_uuid=self.identification.note_uuid,
            structured=False,
            requested_date=Helper.str2date(instruction.parameters["date"]),
            reason_for_visit=instruction.parameters["reasonForVisit"],
            comment=instruction.parameters["comment"],
        )
        #
        idx = instruction.parameters["visitTypeIndex"]
        if not (0 <= idx < len(self.cache.existing_note_types())):
            idx = 0

        note_type = self.cache.existing_note_types()[idx]
        result.note_type_id = note_type.uuid
        self.add_code2description(note_type.uuid, note_type.label)
        #
        if "reasonForVisitIndex" in instruction.parameters:
            if (
                0
                <= (idx := instruction.parameters["reasonForVisitIndex"])
                < len(existing := self.cache.existing_reason_for_visits())
            ):
                result.structured = True
                result.reason_for_visit = existing[idx].uuid
                self.add_code2description(existing[idx].uuid, existing[idx].label)
        else:
            result.reason_for_visit = self.command_from_json_custom_prompted(result.reason_for_visit, chatter)

        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        result: dict = {
            "visitType": "",
            "visitTypeIndex": 0,
            "date": None,
            "reasonForVisit": "",
            "comment": "",
        }
        if self.settings.structured_rfv:
            result |= {
                "reasonForVisitIndex": -1,
            }
        return result

    def command_parameters_schemas(self) -> list[dict]:
        visits = [item.label for item in self.cache.existing_note_types()]
        fields: dict = {
            "visitType": {
                "type": "string",
                "description": "Type of visit",
                "enum": visits,
            },
            "visitTypeIndex": {
                "type": "integer",
                "description": "Index of the visitType",
                "minimum": 0,
                "maximum": len(visits) - 1,
            },
            "date": {
                "type": ["string", "null"],
                "description": "Date of the follow up encounter in YYYY-MM-DD format",
                "format": "date",
                "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
            },
            "reasonForVisit": {
                "type": "string",
                "description": "The main reason for the follow up encounter, as free text",
            },
            "comment": {
                "type": "string",
                "description": "Information related to the scheduling itself, as free text",
            },
        }
        required_fields: list[str] = ["visitType", "visitTypeIndex", "date", "reasonForVisit", "comment"]
        if self.settings.structured_rfv:
            options: list[str] = [r.label for r in self.cache.existing_reason_for_visits()]
            fields |= {
                "reasonForVisit": {
                    "type": "string",
                    "description": "The main reason for the follow up encounter",
                    "enum": options,
                },
                "reasonForVisitIndex": {
                    "type": "integer",
                    "description": "The index of the reason for visit",
                    "minimum": 0,
                    "maximum": len(options) - 1,
                },
            }
            required_fields.append("reasonForVisitIndex")

        return [
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "array",
                "minItems": 1,
                "maxItems": 1,
                "items": {
                    "type": "object",
                    "properties": fields,
                    "required": required_fields,
                    "additionalProperties": False,
                },
            }
        ]

    def instruction_description(self) -> str:
        result = (
            "Any follow up encounter, either virtually or in person. "
            "There can be only one such instruction in the whole discussion, "
            "so if one was already found, just update it by intelligently merging all key information."
        )
        if self.custom_prompt():
            result += (
                " For documentation purposes, always include the relevant parts of the transcript for reference, "
                "including any previous sections when merging."
            )
        return result

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return bool(self.cache.existing_note_types())
