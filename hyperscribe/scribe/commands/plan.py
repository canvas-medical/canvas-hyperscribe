from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.plan import PlanCommand

from hyperscribe.scribe.commands.base import CommandParser


class PlanParser(CommandParser):
    command_type = "plan"
    data_field = "narrative"

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        return PlanCommand(
            narrative=str(data.get("narrative", "")),
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
