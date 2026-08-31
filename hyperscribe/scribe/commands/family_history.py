from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.family_history import FamilyHistoryCommand

from hyperscribe.scribe.commands.base import CommandParser

SNOMED_SYSTEM = "http://snomed.info/sct"


class FamilyHistoryParser(CommandParser):
    command_type = "familyHistory"

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        condition_code = data.get("condition_code")
        condition_display = data.get("condition_display", "")

        family_history: str | dict | None = None
        if condition_code:
            family_history = {
                "system": SNOMED_SYSTEM,
                "code": condition_code,
                "display": condition_display,
            }
        elif condition_display:
            family_history = condition_display

        return FamilyHistoryCommand(
            family_history=family_history,
            relative=data.get("relative") or None,
            note=data.get("note") or None,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
