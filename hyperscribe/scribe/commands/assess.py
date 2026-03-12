from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.assess import AssessCommand

from hyperscribe.scribe.commands.base import CommandParser


def _parse_status(value: Any) -> AssessCommand.Status | None:
    if value is None:
        return None
    for status in AssessCommand.Status:
        if status.value == value:
            return status
    return None


class AssessParser(CommandParser):
    """Parser for assess commands created by the frontend A&P split."""

    command_type = "assess"
    data_field = None

    def extract(self, text: str) -> None:
        return None

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        return AssessCommand(
            condition_id=data.get("condition_id") or "",
            narrative=data.get("narrative") or "",
            background=data.get("background") or "",
            status=_parse_status(data.get("status")),
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
