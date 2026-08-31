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

    def validate(self, data: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        # Hard block (server-side guard): a diagnose command must carry an ICD-10
        # code. The frontend blocks approval of an uncoded diagnosis; this mirrors
        # that on the insert path so the requirement can't be bypassed via the API.
        # (A diagnosis that matched an active problem flips to ``assess`` upstream
        # and is built by a different parser, so it never reaches here uncoded.)
        if not (data.get("icd10_code") or "").strip():
            errors.append("Diagnosis is missing an ICD-10 code")
        if len(data.get("today_assessment") or "") > 2048:
            errors.append("Assessment text exceeds 2048 characters")
        return errors

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        return DiagnoseCommand(
            icd10_code=data.get("icd10_code") or "",
            today_assessment=(data.get("today_assessment") or "")[:2048],
            background=data.get("background") or "",
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
