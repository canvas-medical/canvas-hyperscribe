from __future__ import annotations

from abc import ABC, abstractmethod

from hyperscribe.scribe.models import (
    AsyncJob,
    ClinicalNote,
    NormalizedData,
    PatientContext,
    Transcript,
)


class ScribeBackend(ABC):
    """A scribe backend handles: transcription, note generation, and structured data extraction."""

    @abstractmethod
    def transcribe(self, audio: bytes) -> Transcript: ...

    @abstractmethod
    def transcribe_async_start(self, file_url: str) -> str: ...

    @abstractmethod
    def transcribe_async_poll(self, job_id: str) -> AsyncJob | Transcript: ...

    @abstractmethod
    def generate_note(
        self,
        transcript: Transcript,
        *,
        patient_context: PatientContext | None = None,
    ) -> ClinicalNote: ...

    @abstractmethod
    def generate_normalized_data(self, note: ClinicalNote) -> NormalizedData: ...
