from canvas_sdk.commands.commands.assess import AssessCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class Assess(Base):
    @classmethod
    def command_type(cls) -> str:
        return "AssessCommand"

    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_ASSESS

    @classmethod
    def note_section(cls) -> str:
        return Constants.NOTE_SECTION_ASSESSMENT

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if (narrative := data.get("narrative")) and (condition := data.get("condition", {}).get("text")):
            return CodedItem(label=f"{condition}: {narrative}", code="", uuid="")
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        # Suppress commands for conditions not actually discussed
        raw_assessment = instruction.parameters["assessment"]
        if self.is_filler_narrative(raw_assessment):
            return None

        condition_id: str | None = None
        if matched := self.resolve_item_by_index(
            self.cache.current_conditions(),
            instruction.parameters["conditionIndex"],
            instruction.parameters.get("condition"),
        ):
            condition_id = matched.uuid
            self.add_code2description(matched.uuid, matched.label)

        # Get field values with template permission checks
        background = (
            self.fill_template_content(instruction.parameters["rationale"], "background", instruction, chatter)
            if self.can_edit_field("background")
            else ""
        )
        narrative = (
            self.fill_template_content(raw_assessment, "narrative", instruction, chatter)
            if self.can_edit_field("narrative")
            else ""
        )
        if narrative:
            narrative = self.post_process_narrative(narrative)

        return InstructionWithCommand.add_command(
            instruction,
            AssessCommand(
                condition_id=condition_id,
                background=background,
                status=Helper.enum_or_none(instruction.parameters["status"], AssessCommand.Status),
                narrative=narrative,
                note_uuid=self.identification.note_uuid,
            ),
        )

    def command_parameters(self) -> dict:
        return {
            "condition": None,
            "conditionIndex": -1,
            "rationale": "",
            "status": "",
            "assessment": "",
        }

    def command_parameters_schemas(self) -> list[dict]:
        statuses = [status.value for status in AssessCommand.Status]
        conditions = [condition.label for condition in self.cache.current_conditions()]
        return [
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "array",
                "minItems": 1,
                "maxItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "condition": {
                            "type": ["string", "null"],  # could be null if the condition is not committed yet
                            "description": "The condition to assess",
                            "enum": conditions + [None],
                        },
                        "conditionIndex": {
                            "type": "integer",
                            "description": "Index of the Condition to assess, or -1",
                            "minimum": -1,
                            "maximum": len(conditions) - 1,
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Rationale about the current assessment, as free text",
                        },
                        "status": {
                            "type": "string",
                            "description": "Status of the condition",
                            "enum": statuses,
                        },
                        "assessment": {
                            "type": "string",
                            "description": (
                                "Today's assessment of the condition, structured with "
                                "two labeled sections separated by a newline:\n"
                                "Assessment: 1-3 sentences combining clinical symptoms "
                                "with functional observations, "
                                "summarizing the status, history, and any barriers "
                                "to treatment.\n"
                                "Plan: a direct, bulleted list of actions. "
                                "Include specific barriers to care if mentioned "
                                "in the transcript.\n"
                                "Separate the Assessment and Plan sections "
                                "with a blank line for readability."
                            ),
                        },
                    },
                    "required": ["condition", "conditionIndex", "rationale", "status", "assessment"],
                    "additionalProperties": False,
                },
            }
        ]

    def instruction_description(self) -> str:
        text = ", ".join([f"{condition.label}" for condition in self.cache.current_conditions()])
        return (
            f"Today's assessment of an EXISTING condition already in the patient's chart ({text}). "
            "Use this instruction ONLY when the provider EXPLICITLY discusses, evaluates, reviews, or mentions "
            "a specific existing condition during the visit — including current status, symptoms, "
            "treatment response, or management plan related to the condition. "
            "Do NOT create an assessment for a condition that is not explicitly mentioned in the transcript. "
            "If a condition is not discussed during the visit, do NOT generate any instruction for it. "
            "Never produce filler text such as 'not discussed' or 'no update available'. "
            "There can be only one assessment per condition per instruction, and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        text = ", ".join(
            [f"{condition.label} (ICD-10: {condition.code})" for condition in self.cache.current_conditions()],
        )
        return f"'{self.class_name()}' has to be related to one of the following conditions: {text}"

    def is_available(self) -> bool:
        editable = any([self.can_edit_field(field) for field in ["background", "narrative"]])
        return editable and bool(self.cache.current_conditions())
