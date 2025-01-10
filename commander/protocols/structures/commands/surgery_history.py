from canvas_sdk.commands.commands.past_surgical_history import PastSurgicalHistoryCommand

from commander.protocols.structures.commands.base import Base


class SurgeryHistory(Base):
    def from_json(self, parameters: dict) -> PastSurgicalHistoryCommand:
        return PastSurgicalHistoryCommand(
            past_surgical_history=parameters["surgery"],
            approximate_date=self.str2date(parameters["approximateDate"]).date(),
            comment=parameters["comment"],
        )

    def parameters(self) -> dict:
        return {
            "surgery": "medical name of the surgery",
            "approximateDate": "YYYY-MM-DD",
            "comment": "free text",
        }

    def information(self) -> str:
        return ("Any past surgery. "
                "There can be only one surgery per instruction, and no instruction in the lack of.")

    def is_available(self) -> bool:
        return True
