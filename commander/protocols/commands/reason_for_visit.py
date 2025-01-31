from canvas_sdk.commands.commands.reason_for_visit import ReasonForVisitCommand

from commander.protocols.commands.base import Base


class ReasonForVisit(Base):
    @classmethod
    def schema_key(cls) -> str:
        return "reasonForVisit"

    def command_from_json(self, parameters: dict) -> None | ReasonForVisitCommand:
        return ReasonForVisitCommand(
            comment=parameters["reasonForVisit"],
            note_uuid=self.note_uuid,
        )

    def command_parameters(self) -> dict:
        return {
            "reasonForVisit": "description of the reason of the visit, as free text",
        }

    def instruction_description(self) -> str:
        result = ("Patient's reported reason for the visit. "
                  "There can be multiple reasons within an instruction.")
        if self.settings.allow_update:
            result += (" There can be only one such instruction in the whole discussion, "
                       "so if one was already found, just update it by intelligently merging all reasons.")

        return result

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
