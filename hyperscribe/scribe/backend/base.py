from __future__ import annotations

from abc import ABC, abstractmethod

from hyperscribe.scribe.backend.models import (
    ClinicalNote,
    NormalizedData,
    PatientContext,
    Transcript,
    TranscriptItem,
)


class ScribeBackend(ABC):
    """A scribe backend handles: real-time transcription, note generation, and structured data extraction."""

    @abstractmethod
    def start_session(self) -> None:
        """Open a transcription session (e.g., WebSocket connection)."""
        ...

    @abstractmethod
    def send_audio(self, audio: bytes) -> None:
        """Send a raw audio chunk to the backend."""
        ...

    @abstractmethod
    def get_transcript_updates(self) -> list[TranscriptItem]:
        """Non-blocking drain of transcript items received since last call.
        Returns both partial (is_final=False) and final (is_final=True) items."""
        ...

    @abstractmethod
    def end_session(self) -> Transcript:
        """Signal end of audio, wait for remaining items, close session.
        Returns complete Transcript with only final items."""
        ...

    @abstractmethod
    def generate_note(
        self,
        transcript: Transcript,
        *,
        patient_context: PatientContext | None = None,
    ) -> ClinicalNote: ...

    @abstractmethod
    def generate_normalized_data(self, note: ClinicalNote) -> NormalizedData: ...
