from __future__ import annotations

from datetime import date
from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.medical_history import MedicalHistoryCommand

from hyperscribe.scribe.commands.base import CommandParser


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


class MedicalHistoryParser(CommandParser):
    command_type = "medicalHistory"

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        return MedicalHistoryCommand(
            past_medical_history=data.get("past_medical_history") or None,
            approximate_start_date=_parse_date(data.get("approximate_start_date")),
            approximate_end_date=_parse_date(data.get("approximate_end_date")),
            comments=data.get("comments") or None,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
