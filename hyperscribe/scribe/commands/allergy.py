from __future__ import annotations

import re
from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.allergy import (
    Allergen,
    AllergenType,
    AllergyCommand,
)

from hyperscribe.scribe.backend.models import CommandProposal
from hyperscribe.scribe.commands.base import CommandParser

_BULLET_RE = re.compile(r"^(?:\d+[.)]\s*|[-*]\s+)")


def _parse_allergy_lines(text: str) -> list[str]:
    """Split text into individual allergy lines, stripping bullet markers."""
    lines: list[str] = []
    for raw in text.split("\n"):
        cleaned = _BULLET_RE.sub("", raw).strip()
        if cleaned:
            lines.append(cleaned)
    return lines


class AllergyParser(CommandParser):
    command_type = "allergy"

    def extract(self, text: str) -> CommandProposal | None:
        lines = _parse_allergy_lines(text)
        if not lines:
            return None
        return CommandProposal(
            command_type=self.command_type,
            display=lines[0],
            data={
                "allergy_text": lines[0],
                "concept_id": None,
                "concept_id_type": None,
            },
        )

    def extract_all(self, text: str) -> list[CommandProposal]:
        return [
            CommandProposal(
                command_type=self.command_type,
                display=line,
                data={
                    "allergy_text": line,
                    "concept_id": None,
                    "concept_id_type": None,
                },
            )
            for line in _parse_allergy_lines(text)
        ]

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        allergy_text = str(data.get("allergy_text", ""))
        concept_id = data.get("concept_id")
        concept_id_type = data.get("concept_id_type")

        allergen: Allergen | None = None
        if concept_id is not None:
            allergen = Allergen(
                concept_id=int(concept_id),
                concept_type=AllergenType(int(concept_id_type or 1)),
            )

        raw_severity = data.get("severity")
        severity = AllergyCommand.Severity(raw_severity) if raw_severity in {"mild", "moderate", "severe"} else None

        return AllergyCommand(
            allergy=allergen,
            narrative=data.get("reaction") or allergy_text,
            severity=severity,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
