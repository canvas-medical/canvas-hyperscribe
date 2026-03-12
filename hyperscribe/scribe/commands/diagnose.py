from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.diagnose import DiagnoseCommand

from hyperscribe.scribe.commands.base import CommandParser


class DiagnoseParser(CommandParser):
    """Parser for diagnose commands created by the frontend A&P split."""

    command_type = "diagnose"
    data_field = None

    def extract(self, text: str) -> None:
        return None

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        return DiagnoseCommand(
            icd10_code=data.get("icd10_code") or "",
            today_assessment=data.get("today_assessment") or "",
            background=data.get("background") or "",
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
