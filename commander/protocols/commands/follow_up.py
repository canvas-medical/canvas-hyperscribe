from canvas_sdk.commands.commands.follow_up import FollowUpCommand

from commander.protocols.commands.base import Base
from commander.protocols.helper import Helper


class FollowUp(Base):
    @classmethod
    def schema_key(cls) -> str:
        return "followUp"

    def command_from_json(self, parameters: dict) -> None | FollowUpCommand:
        idx = parameters["visitTypeIndex"]
        if not (0 <= idx < len(self.cache.existing_note_types())):
            idx = 0
        note_type_uuid = self.cache.existing_note_types()[idx].uuid

        return FollowUpCommand(
            note_uuid=self.note_uuid,
            structured=False,
            requested_date=Helper.str2date(parameters["date"]),
            note_type_id=note_type_uuid,
            reason_for_visit=parameters["reasonForVisit"],
            comment=parameters["comment"],
        )

    def command_parameters(self) -> dict:
        visits = "/".join([f"{item.label} (index:{idx})" for idx, item in enumerate(self.cache.existing_note_types())])
        return {
            "visitType": f"one of: {visits}",
            "visitTypeIndex": "index of the visitType, as integer",
            "date": "date of the follow up encounter, as YYYY-MM-DD",
            "reasonForVisit": "the main reason for the follow up encounter, as free text",
            "comment": "information related to the scheduling itself, as free text",
        }

    def instruction_description(self) -> str:
        return ("Any follow up encounter, either virtually or in person. "
                "There can be only one such instruction in the whole discussion, "
                "so if one was already found, just update it by intelligently merging all key information.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return bool(self.cache.existing_note_types())
