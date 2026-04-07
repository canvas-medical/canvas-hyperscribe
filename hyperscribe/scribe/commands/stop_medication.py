from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.stop_medication import StopMedicationCommand

from hyperscribe.scribe.commands.base import CommandParser


class StopMedicationParser(CommandParser):
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

    def pending_metadata(self, command: _BaseCommand, proposal: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if proposal and proposal.get("data", {}).get("alert_facility"):
            return {
                "command_uuid": command.command_uuid,
                "command_type": self.command_type,
                "note_uuid": command.note_uuid,
                "metadata": {"alert_facility": "true"},
            }
        return None

    def build_stub(self, command_uuid: str, note_uuid: str) -> _BaseCommand:
        return StopMedicationCommand(command_uuid=command_uuid, note_uuid=note_uuid)
