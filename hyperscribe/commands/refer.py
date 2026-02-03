from canvas_sdk.commands import ReferCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.selector_chat import SelectorChat
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class Refer(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_REFER

    @classmethod
    def note_section(cls) -> str:
        return Constants.NOTE_SECTION_PLAN

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if (refer_to := data.get("refer_to")) and (text := refer_to.get("text")):
            priority = data.get("priority") or "n/a"
            question = data.get("clinical_question") or "n/a"
            notes_to_specialist = data.get("notes_to_specialist") or "n/a"
            indications = (
                "/".join(
                    [
                        indication
                        for question in (data.get("indications") or [])
                        if (indication := question.get("text"))
                    ],
                )
                or "n/a"
            )
            documents = (
                "/".join(
                    [
                        document
                        for included in (data.get("documents_to_include") or [])
                        if (document := included.get("text"))
                    ],
                )
                or "n/a"
            )
            return CodedItem(
                label=f"referred to {text}: {notes_to_specialist} (priority: {priority}, question: {question}, "
                f"documents: {documents}, related conditions: {indications})",
                code="",
                uuid="",
            )
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        # Get field values with template permission checks
        notes_to_specialist: str | None = None
        if self.can_edit_field("notes_to_specialist"):
            notes_to_specialist = instruction.parameters["notesToSpecialist"]
            notes_to_specialist = self.enhance_with_template_instructions(
                notes_to_specialist, "notes_to_specialist", instruction, chatter
            )

        comment: str | None = None
        if self.can_edit_field("comment"):
            comment = instruction.parameters["comment"]
            comment = self.enhance_with_template_instructions(comment, "comment", instruction, chatter)

        # If neither field can be edited, skip this command
        if notes_to_specialist is None and comment is None:
            return None

        zip_codes = self.cache.practice_setting("serviceAreaZipCodes")
        information = instruction.parameters["referredServiceProvider"]["specialty"]
        if names := instruction.parameters["referredServiceProvider"]["names"]:
            information = (
                f"{information} {names}"  # <-- the order is important for the search in the Canvas Science service
            )

        provider = SelectorChat.contact_from(instruction, chatter, information, zip_codes)
        result = ReferCommand(
            service_provider=provider,
            clinical_question=Helper.enum_or_none(
                instruction.parameters["clinicalQuestion"],
                ReferCommand.ClinicalQuestion,
            ),
            priority=Helper.enum_or_none(instruction.parameters["priority"], ReferCommand.Priority),
            notes_to_specialist=notes_to_specialist or "",
            comment=comment or "",
            note_uuid=self.identification.note_uuid,
            diagnosis_codes=[],
        )
        # retrieve the linked conditions
        conditions = []
        for condition in instruction.parameters["conditions"]:
            item = SelectorChat.condition_from(
                instruction,
                chatter,
                condition["conditionKeywords"].split(","),
                condition["ICD10"].split(","),
                comment or "",
            )
            if item.code:
                conditions.append(item)
                result.diagnosis_codes.append(item.code)
                self.add_code2description(item.code, item.label)

        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        return {
            "referredServiceProvider": {"specialty": "", "names": ""},
            "clinicalQuestion": "",
            "priority": "",
            "notesToSpecialist": "",
            "comment": "",
            "conditions": [],
        }

    def command_parameters_schemas(self) -> list[dict]:
        return [
            {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "referredServiceProvider": {
                            "type": "object",
                            "properties": {
                                "specialty": {
                                    "type": "string",
                                    "description": "the specialty of the referred provider, required",
                                },
                                "names": {
                                    "type": "string",
                                    "description": "the names of the practice and/or of the referred provider, "
                                    "or empty",
                                },
                            },
                            "required": ["specialty", "names"],
                        },
                        "clinicalQuestion": {
                            "type": "string",
                            "enum": [item.value for item in ReferCommand.ClinicalQuestion],
                        },
                        "priority": {
                            "type": "string",
                            "enum": [item.value for item in ReferCommand.Priority],
                        },
                        "notesToSpecialist": {
                            "type": "string",
                            "description": "note or question to be sent to the referred specialist, "
                            "concise, directly derived from the transcript content and required",
                        },
                        "comment": {
                            "type": "string",
                            "description": "Direct clinical reasoning statement, derived only from transcript "
                            "content. Express the medical findings and purpose of the referral "
                            "as a concise clinical note, without introducing phrases like "
                            "'referral' or 'rationale'.",
                        },
                        "conditions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "conditionKeywords": {
                                        "type": "string",
                                        "description": "Comma-separated keywords to find in a database "
                                        "(using OR criteria) the condition related to the referral.",
                                    },
                                    "ICD10": {
                                        "type": "string",
                                        "description": "Comma-separated ICD-10 codes (up to 5) for the condition "
                                        "related to the referral.",
                                    },
                                },
                                "required": ["conditionKeywords", "ICD10"],
                            },
                        },
                    },
                    "required": [
                        "referredServiceProvider",
                        "clinicalQuestion",
                        "priority",
                        "notesToSpecialist",
                        "comment",
                        "conditions",
                    ],
                },
            }
        ]

    def instruction_description(self) -> str:
        return (
            "Referral to a specialist, including the rationale and the targeted conditions. "
            "There can be one and only one referral in an instruction with all necessary information, "
            "and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
