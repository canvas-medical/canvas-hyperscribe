from canvas_sdk.commands.commands.reason_for_visit import ReasonForVisitCommand

from commander.protocols.structures.commands.base import Base


class ReasonForVisit(Base):
    def from_json(self, parameters: dict) -> None | ReasonForVisitCommand:
        return ReasonForVisitCommand(
            comment=parameters["reasonForVisit"],
            note_uuid=self.note_uuid,
        )

    def parameters(self) -> dict:
        return {
            "reasonForVisit": "free text",
        }

    def information(self) -> str:
        return ("Patient's reported reason for the visit. "
                "There can be multiple reasons within an instruction.")

    def is_available(self) -> bool:
        return True
