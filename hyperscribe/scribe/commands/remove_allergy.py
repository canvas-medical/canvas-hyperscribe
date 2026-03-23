from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.remove_allergy import RemoveAllergyCommand

from hyperscribe.scribe.commands.base import CommandParser


class RemoveAllergyParser(CommandParser):
    """Parser for remove allergy commands created by the frontend."""

    command_type = "remove_allergy"
    data_field = None

    def extract(self, text: str) -> None:
        return None

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        return RemoveAllergyCommand(
            allergy_id=data.get("allergy_id") or None,
            narrative=data.get("narrative") or None,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
