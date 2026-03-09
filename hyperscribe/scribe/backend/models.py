from __future__ import annotations

from typing import Any


class TranscriptItem:
    def __init__(
        self,
        *,
        text: str,
        speaker: str,
        start_offset_ms: int,
        end_offset_ms: int,
        item_id: str = "",
        is_final: bool = True,
    ) -> None:
        self.text = text
        self.speaker = speaker
        self.start_offset_ms = start_offset_ms
        self.end_offset_ms = end_offset_ms
        self.item_id = item_id
        self.is_final = is_final

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TranscriptItem):
            return NotImplemented
        return (
            self.text == other.text
            and self.speaker == other.speaker
            and self.start_offset_ms == other.start_offset_ms
            and self.end_offset_ms == other.end_offset_ms
            and self.item_id == other.item_id
            and self.is_final == other.is_final
        )


class Transcript:
    def __init__(self, *, items: list[TranscriptItem] | None = None) -> None:
        self.items: list[TranscriptItem] = items if items is not None else []


class NoteSection:
    def __init__(self, *, key: str, title: str, text: str) -> None:
        self.key = key
        self.title = title
        self.text = text


class ClinicalNote:
    def __init__(self, *, title: str, sections: list[NoteSection] | None = None) -> None:
        self.title = title
        self.sections: list[NoteSection] = sections if sections is not None else []


class CodingEntry:
    def __init__(self, *, system: str, code: str, display: str) -> None:
        self.system = system
        self.code = code
        self.display = display


class Condition:
    def __init__(
        self,
        *,
        display: str,
        clinical_status: str,
        coding: list[CodingEntry] | None = None,
    ) -> None:
        self.display = display
        self.clinical_status = clinical_status
        self.coding: list[CodingEntry] = coding if coding is not None else []


class Observation:
    def __init__(
        self,
        *,
        display: str,
        value: str,
        unit: str,
        coding: list[CodingEntry] | None = None,
    ) -> None:
        self.display = display
        self.value = value
        self.unit = unit
        self.coding: list[CodingEntry] = coding if coding is not None else []


class NormalizedData:
    def __init__(
        self,
        *,
        conditions: list[Condition] | None = None,
        observations: list[Observation] | None = None,
    ) -> None:
        self.conditions: list[Condition] = conditions if conditions is not None else []
        self.observations: list[Observation] = observations if observations is not None else []


class CommandProposal:
    def __init__(
        self,
        *,
        command_type: str,
        display: str,
        data: dict[str, Any],
        selected: bool = True,
    ) -> None:
        self.command_type = command_type
        self.display = display
        self.data = data
        self.selected = selected


class PatientContext:
    def __init__(
        self,
        *,
        name: str,
        birth_date: str,
        gender: str,
        encounter_diagnoses: list[CodingEntry] | None = None,
    ) -> None:
        self.name = name
        self.birth_date = birth_date
        self.gender = gender
        self.encounter_diagnoses: list[CodingEntry] = encounter_diagnoses if encounter_diagnoses is not None else []
