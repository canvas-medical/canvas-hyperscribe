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
        result.note_type_id = self.cache.existing_note_types()[idx].uuid
        #
        if "reasonForVisitIndex" in instruction.parameters:
            if (
                0
                <= (idx := instruction.parameters["reasonForVisitIndex"])
                < len(existing := self.cache.existing_reason_for_visits())
            ):
                result.structured = True
                result.reason_for_visit = existing[idx].uuid

        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        reason_for_visit = {}
        if self.settings.structured_rfv:
            options = "/".join([r.label for r in self.cache.existing_reason_for_visits()])
            reason_for_visit = {
                "reasonForVisit": f"one of: {options}",
                "reasonForVisitIndex": "the index of the reason for visit, as integer",
            }

        visits = "/".join([f"{item.label} (index:{idx})" for idx, item in enumerate(self.cache.existing_note_types())])
        return {
            "visitType": f"one of: {visits}",
            "visitTypeIndex": "index of the visitType, as integer",
            "date": "date of the follow up encounter, as YYYY-MM-DD",
            "reasonForVisit": "the main reason for the follow up encounter, as free text",
            "comment": "information related to the scheduling itself, as free text",
        } | reason_for_visit

    def instruction_description(self) -> str:
        return (
            "Any follow up encounter, either virtually or in person. "
            "There can be only one such instruction in the whole discussion, "
            "so if one was already found, just update it by intelligently merging all key information."
        )

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return bool(self.cache.existing_note_types())
