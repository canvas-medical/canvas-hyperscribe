from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.lab_order import LabOrderCommand

from hyperscribe.scribe.commands.base import CommandParser


class LabOrderParser(CommandParser):
    command_type = "lab_order"
    data_field = "comment"

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        return LabOrderCommand(
            lab_partner=data.get("lab_partner") or None,
            tests_order_codes=data.get("tests_order_codes") or [],
            diagnosis_codes=data.get("diagnosis_codes") or [],
            fasting_required=bool(data.get("fasting_required")),
            comment=data.get("comment") or None,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
