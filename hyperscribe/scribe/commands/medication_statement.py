from __future__ import annotations

import re
from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.medication_statement import MedicationStatementCommand
from canvas_sdk.commands.constants import CodeSystems, Coding
from canvas_sdk.v1.data.medication import MedicationCoding
from canvas_sdk.v1.data.note import Note

from hyperscribe.scribe.backend.models import CommandProposal
from hyperscribe.scribe.commands.base import CommandParser

_BULLET_RE = re.compile(r"^(?:\d+[.)]\s*|[-*]\s+)")


def _parse_medication_lines(text: str) -> list[str]:
    """Split text into individual medication lines, stripping bullet markers."""
    lines: list[str] = []
    for raw in text.split("\n"):
        cleaned = _BULLET_RE.sub("", raw).strip()
        if cleaned:
            lines.append(cleaned)
    return lines


def _unstructured_coding(medication_text: str) -> dict[str, str]:
    return {
        "system": CodeSystems.UNSTRUCTURED,
        "code": medication_text,
        "display": medication_text,
    }


class MedicationParser(CommandParser):
    command_type = "medication_statement"

    def extract(self, text: str) -> CommandProposal | None:
        lines = _parse_medication_lines(text)
        if not lines:
            return None
        return CommandProposal(
            command_type=self.command_type,
            display=lines[0],
            data={
                "medication_text": lines[0],
                "fdb_code": _unstructured_coding(lines[0]),
            },
        )

    def extract_all(self, text: str) -> list[CommandProposal]:
        return [
            CommandProposal(
                command_type=self.command_type,
                display=line,
                data={
                    "medication_text": line,
                    "fdb_code": _unstructured_coding(line),
                },
            )
            for line in _parse_medication_lines(text)
        ]

    def annotate_duplicates(self, proposals: list[CommandProposal], note: Note) -> None:
        med_proposals = [p for p in proposals if p.command_type == self.command_type]
        if not med_proposals:
            return
        patient = note.patient
        if patient is None:
            return
        active_labels = set(
            MedicationCoding.objects.filter(
                medication__patient=patient,
                medication__status="active",
            ).values_list("display", flat=True)
        )
        active_labels_lower = {label.lower() for label in active_labels if label}
        for proposal in med_proposals:
            med_text = proposal.data.get("medication_text", "").lower()
            if not med_text:
                continue
            for label in active_labels_lower:
                if med_text in label or label in med_text:
                    proposal.already_documented = True
                    break

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        medication_text = str(data.get("medication_text", ""))
        raw_fdb = data.get("fdb_code")
        fdb_code: str | Coding
        if isinstance(raw_fdb, dict):
            system = str(raw_fdb.get("system", CodeSystems.UNSTRUCTURED))
            if system != CodeSystems.UNSTRUCTURED:
                # Structured FDB medication — pass the plain code string
                # (matches how the copilot flow sets fdb_code).
                fdb_code = str(raw_fdb.get("code", ""))
            else:
                fdb_code = Coding(
                    system=CodeSystems.UNSTRUCTURED,
                    code=str(raw_fdb.get("code", "")),
                    display=str(raw_fdb.get("display", medication_text)),
                )
        elif raw_fdb:
            fdb_code = str(raw_fdb)
        else:
            fdb_code = Coding(
                system=CodeSystems.UNSTRUCTURED,
                code=medication_text,
                display=medication_text,
            )
        return MedicationStatementCommand(
            fdb_code=fdb_code,
            sig=data.get("sig") or None,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
