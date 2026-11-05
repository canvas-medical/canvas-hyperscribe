from __future__ import annotations

from datetime import date
from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.past_surgical_history import PastSurgicalHistoryCommand

from hyperscribe.scribe.commands.base import CommandParser

SNOMED_SYSTEM = "http://snomed.info/sct"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


class SurgicalHistoryParser(CommandParser):
    command_type = "surgicalHistory"

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        procedure_code = data.get("procedure_code")
        procedure_display = data.get("procedure_display", "")

        past_surgical_history: str | dict | None = None
        if procedure_code:
            past_surgical_history = {
                "system": SNOMED_SYSTEM,
                "code": procedure_code,
                "display": procedure_display,
            }
        elif procedure_display:
            past_surgical_history = procedure_display

        return PastSurgicalHistoryCommand(
            past_surgical_history=past_surgical_history,
            approximate_date=_parse_date(data.get("approximate_date")),
            comment=data.get("comment") or None,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
