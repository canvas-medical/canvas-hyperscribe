from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.stop_medication import StopMedicationCommand

from hyperscribe.scribe.commands.base import AlertFacilityMetadataMixin, CommandParser


class StopMedicationParser(AlertFacilityMetadataMixin, CommandParser):
    """Parser for stop medication commands created by the frontend."""

    command_type = "stop_medication"
    data_field = None

    def extract(self, text: str) -> None:
        return None

    def validate(self, data: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if len(data.get("rationale") or "") > 1024:
            errors.append("Rationale exceeds 1024 characters")
        return errors

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        return StopMedicationCommand(
            medication_id=data.get("medication_id") or None,
            rationale=(data.get("rationale") or "")[:1024] or None,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )

    def build_stub(self, command_uuid: str, note_uuid: str) -> _BaseCommand:
        return StopMedicationCommand(command_uuid=command_uuid, note_uuid=note_uuid)
