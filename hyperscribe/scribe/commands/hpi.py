from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.history_present_illness import HistoryOfPresentIllnessCommand

from hyperscribe.scribe.commands.base import CommandParser


class HpiParser(CommandParser):
    command_type = "hpi"
    data_field = "narrative"

    def build(self, data: dict[str, Any], note_uuid: str) -> _BaseCommand:
        return HistoryOfPresentIllnessCommand(
            narrative=str(data.get("narrative", "")),
            note_uuid=note_uuid,
        )
