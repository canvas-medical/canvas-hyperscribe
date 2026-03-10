from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.imaging_order import ImagingOrderCommand

from hyperscribe.scribe.commands.base import CommandParser


class ImagingOrderParser(CommandParser):
    command_type = "imaging_order"
    data_field = None

    def extract(self, text: str) -> None:
        return None

    def build(self, data: dict[str, Any], note_uuid: str) -> _BaseCommand:
        priority = None
        raw_priority = data.get("priority")
        if raw_priority == "Routine":
            priority = ImagingOrderCommand.Priority.ROUTINE
        elif raw_priority == "Urgent":
            priority = ImagingOrderCommand.Priority.URGENT

        return ImagingOrderCommand(
            comment=data.get("comment") or None,
            priority=priority,
            note_uuid=note_uuid,
        )
