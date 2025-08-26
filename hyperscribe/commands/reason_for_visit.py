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
            comment=instruction.parameters["reasonForVisit"],
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
        if self.settings.structured_rfv:
            options = "/".join([r.label for r in self.cache.existing_reason_for_visits()])
            return {
                "reasonForVisit": f"one of: {options}",
                "reasonForVisitIndex": "the index of the reason for visit, as integer",
            }
        return {"reasonForVisit": "extremely concise description of the reason or impetus for the visit, as free text"}

    def instruction_description(self) -> str:
        if self.settings.structured_rfv:
            text = ", ".join([r.label for r in self.cache.existing_reason_for_visits()])
            return (
                f"Patient's reported reason or impetus for the visit within: {text}. "
                "There can be only one such instruction in the whole discussion. "
                "So, if one was already found, simply update it by intelligently."
            )

        return (
            "Patient's reported reason or impetus for the visit, extremely concise. "
            "There can be multiple reasons within an instruction, "
            "but only one such instruction in the whole discussion. "
            "So, if one was already found, simply update it by intelligently merging all reasons."
        )

    def instruction_constraints(self) -> str:
        if self.settings.structured_rfv:
            text = ", ".join([r.label for r in self.cache.existing_reason_for_visits()])
            return f"'{self.class_name()}' has to be one of the following: {text}"
        return ""

    def is_available(self) -> bool:
        if self.settings.structured_rfv:
            return bool(self.cache.existing_reason_for_visits())
        return True
