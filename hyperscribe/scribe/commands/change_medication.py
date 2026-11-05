from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.change_medication import ChangeMedicationCommand

from hyperscribe.scribe.commands.base import CommandParser


class ChangeMedicationParser(CommandParser):
    command_type = "change_medication"
    data_field = None

    def extract(self, text: str) -> None:
        return None

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        return ChangeMedicationCommand(
            medication_id=data.get("medication_id") or None,
            sig=data.get("sig") or None,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
