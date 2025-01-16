from canvas_sdk.commands.commands.reason_for_visit import ReasonForVisitCommand

from commander.protocols.structures.commands.base import Base


class ReasonForVisit(Base):
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
        return ("Patient's reported reason for the visit. "
                "There can be multiple reasons within an instruction.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
