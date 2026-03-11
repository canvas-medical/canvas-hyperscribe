from __future__ import annotations

import re
from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.vitals import VitalsCommand

from hyperscribe.scribe.backend.models import CommandProposal
from hyperscribe.scribe.commands.base import CommandParser


def _parse_vitals(text: str) -> dict[str, int | float | None]:
    """Parse free-text vitals into structured fields."""
    result: dict[str, int | float | None] = {}
    for line in re.split(r"[,\n]", text):
        line = line.strip()
        if not line:
            continue
        # Blood pressure
        bp_match = re.search(r"(\d+)\s*/\s*(\d+)", line)
        if bp_match and "blood_pressure_systole" not in result:
            result["blood_pressure_systole"] = int(bp_match.group(1))
            result["blood_pressure_diastole"] = int(bp_match.group(2))
            continue
        # Pulse
        m = re.search(r"(?:HR|Heart\s*rate|Pulse)[:\s]*(\d+)", line, re.IGNORECASE)
        if m:
            result["pulse"] = int(m.group(1))
            continue
        # Respiration
        m = re.search(r"(?:RR|Resp(?:iration)?\s*(?:rate)?)[:\s]*(\d+)", line, re.IGNORECASE)
        if m:
            result["respiration_rate"] = int(m.group(1))
            continue
        # O2 saturation
        m = re.search(r"(?:O2|SpO2|Oxygen\s*sat(?:uration)?)[:\s]*(\d+)", line, re.IGNORECASE)
        if m:
            result["oxygen_saturation"] = int(m.group(1))
            continue
        # Temperature
        m = re.search(r"Temp(?:erature)?[:\s]*([\d.]+)", line, re.IGNORECASE)
        if m:
            result["body_temperature"] = float(m.group(1))
            continue
        # Height (feet'inches")
        m = re.search(r"Height[:\s]*(\d+)'(\d+)\"", line, re.IGNORECASE)
        if m:
            result["height"] = int(m.group(1)) * 12 + int(m.group(2))
            continue
        # Weight
        m = re.search(r"Weight[:\s]*(\d+)\s*(?:lbs?|pounds?)", line, re.IGNORECASE)
        if m:
            result["weight_lbs"] = int(m.group(1))
            continue
    return result


class VitalsParser(CommandParser):
    command_type = "vitals"

    def extract(self, text: str) -> CommandProposal | None:
        data = _parse_vitals(text)
        if not data:
            return None
        return CommandProposal(command_type=self.command_type, display=text, data=data)

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        return VitalsCommand(
            height=data.get("height"),
            weight_lbs=data.get("weight_lbs"),
            body_temperature=data.get("body_temperature"),
            blood_pressure_systole=data.get("blood_pressure_systole"),
            blood_pressure_diastole=data.get("blood_pressure_diastole"),
            pulse=data.get("pulse"),
            respiration_rate=data.get("respiration_rate"),
            oxygen_saturation=data.get("oxygen_saturation"),
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
