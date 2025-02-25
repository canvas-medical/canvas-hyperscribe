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
            "reasonForVisit": "extremely concise description of the reason or impetus for the visit, as free text",
        }

    def instruction_description(self) -> str:
        return ("Patient's reported reason or impetus for the visit, extremely concise. "
                "There can be multiple reasons within an instruction, "
                "but only one such instruction in the whole discussion. "
                "So, if one was already found, simply update it by intelligently merging all reasons.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
