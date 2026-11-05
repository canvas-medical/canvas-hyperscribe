from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.perform import PerformCommand

from hyperscribe.scribe.commands.base import CommandParser


class PerformParser(CommandParser):
    """Parser for perform (charge/CPT) commands created by the frontend."""

    command_type = "perform"
    data_field = None

    def extract(self, text: str) -> None:
        return None

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        return PerformCommand(
            cpt_code=data.get("cpt_code") or None,
            notes=data.get("notes") or None,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
