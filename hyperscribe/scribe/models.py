from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TranscriptionStatus(Enum):
    ONGOING = "ongoing"
    FAILED = "failed"
    SUCCEEDED = "succeeded"


@dataclass(frozen=True)
class TranscriptItem:
    text: str
    speaker: str
    start_offset_ms: int
    end_offset_ms: int


@dataclass(frozen=True)
class Transcript:
    items: list[TranscriptItem] = field(default_factory=list)


@dataclass(frozen=True)
class AsyncJob:
    id: str
    status: TranscriptionStatus


@dataclass(frozen=True)
class NoteSection:
    key: str
    title: str
    text: str


@dataclass(frozen=True)
class ClinicalNote:
    title: str
    sections: list[NoteSection] = field(default_factory=list)


@dataclass(frozen=True)
class CodingEntry:
    system: str
    code: str
    display: str


@dataclass(frozen=True)
class Condition:
    display: str
    clinical_status: str
    coding: list[CodingEntry] = field(default_factory=list)


@dataclass(frozen=True)
class Observation:
    display: str
    value: str
    unit: str
    coding: list[CodingEntry] = field(default_factory=list)


@dataclass(frozen=True)
class NormalizedData:
    conditions: list[Condition] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)


@dataclass(frozen=True)
class PatientContext:
    name: str
    birth_date: str
    gender: str
    encounter_diagnoses: list[CodingEntry] = field(default_factory=list)
