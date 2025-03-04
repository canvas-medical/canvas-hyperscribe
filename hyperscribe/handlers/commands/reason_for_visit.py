from canvas_sdk.commands.commands.reason_for_visit import ReasonForVisitCommand

from hyperscribe.handlers.commands.base import Base
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.structures.coded_item import CodedItem


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

    def command_from_json(self, parameters: dict) -> None | ReasonForVisitCommand:
        result = ReasonForVisitCommand(
            comment=parameters["reasonForVisit"],
            note_uuid=self.note_uuid,
        )
        if "reasonForVisitIndex" in parameters:
            if 0 <= (idx := parameters["reasonForVisitIndex"]) < len(existing := self.cache.existing_reason_for_visits()):
                result.structured = True
                result.coding = existing[idx].uuid

        return result

    def command_parameters(self) -> dict:
        if self.settings.structured_rfv:
            options = "/".join([r.label for r in self.cache.existing_reason_for_visits()])
            return {
                "reasonForVisit": f"one of: {options}",
                "reasonForVisitIndex": "the index of the reason for visit, as integer",
            }
        return {
            "reasonForVisit": "extremely concise description of the reason or impetus for the visit, as free text",
        }

    def instruction_description(self) -> str:
        if self.settings.structured_rfv:
            text = ", ".join([r.label for r in self.cache.existing_reason_for_visits()])
            return (f"Patient's reported reason or impetus for the visit within: {text}. "
                    "There can be only one such instruction in the whole discussion. "
                    "So, if one was already found, simply update it by intelligently.")

        return ("Patient's reported reason or impetus for the visit, extremely concise. "
                "There can be multiple reasons within an instruction, "
                "but only one such instruction in the whole discussion. "
                "So, if one was already found, simply update it by intelligently merging all reasons.")

    def instruction_constraints(self) -> str:
        if self.settings.structured_rfv:
            text = ", ".join([r.label for r in self.cache.existing_reason_for_visits()])
            return f"'{self.class_name()}' has to be one of the following: {text}"
        return ""

    def is_available(self) -> bool:
        if self.settings.structured_rfv:
            return bool(self.cache.existing_reason_for_visits())
        return True
