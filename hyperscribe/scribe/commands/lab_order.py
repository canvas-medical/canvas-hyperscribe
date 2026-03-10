from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.lab_order import LabOrderCommand

from hyperscribe.scribe.commands.base import CommandParser


class LabOrderParser(CommandParser):
    command_type = "lab_order"
    data_field = "comment"

    def build(self, data: dict[str, Any], note_uuid: str) -> _BaseCommand:
        return LabOrderCommand(
            comment=data.get("comment") or None,
            note_uuid=note_uuid,
        )
