from canvas_sdk.commands.commands.reason_for_visit import ReasonForVisitCommand

from commander.protocols.commands.base import Base


class ReasonForVisit(Base):
    @classmethod
    def schema_key(cls) -> str:
        return "reasonForVisit"

    def command_from_json(self, parameters: dict) -> None | ReasonForVisitCommand:
        result = ReasonForVisitCommand(
            comment=parameters["reasonForVisit"],
            note_uuid=self.note_uuid,
        )
        if "presetReasonForVisitIndex" in parameters:
            if 0 <= (idx := int(parameters["presetReasonForVisitIndex"])) < len(existing := self.cache.existing_reason_for_visits()):
                result.structured = True
                result.coding = existing[idx].uuid

        return result

    def command_parameters(self) -> dict:
        suggested_reason_for_visits = {}
        if options := "/".join([r.label for r in self.cache.existing_reason_for_visits()]):
            suggested_reason_for_visits = {
                "presetReasonForVisit": f"None or, the one of the following that fully encompasses the reason for visit: {options}",
                "presetReasonForVisitIndex": "the index of the preset reason for visit or -1, as integer",
            }
        return {
            "reasonForVisit": "extremely concise description of the reason or impetus for the visit, as free text",
        } | suggested_reason_for_visits

    def instruction_description(self) -> str:
        return ("Patient's reported reason or impetus for the visit, extremely concise. "
                "There can be multiple reasons within an instruction, "
                "but only one such instruction in the whole discussion. "
                "So, if one was already found, simply update it by intelligently merging all reasons.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
