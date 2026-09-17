from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.resolve_condition import ResolveConditionCommand

from hyperscribe.scribe.commands.base import CommandParser


class ResolveConditionParser(CommandParser):
    """Parser for resolve condition commands created by the frontend."""

    command_type = "resolve_condition"
    data_field = None

    def extract(self, text: str) -> None:
        return None

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        return ResolveConditionCommand(
            condition_id=data.get("condition_id") or None,
            rationale=data.get("rationale") or None,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
