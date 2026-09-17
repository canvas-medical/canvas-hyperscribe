from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.reason_for_visit import ReasonForVisitCommand

from hyperscribe.scribe.commands.base import CommandParser


class RfvParser(CommandParser):
    command_type = "rfv"
    data_field = "comment"

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        return ReasonForVisitCommand(
            comment=str(data.get("comment", "")),
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
