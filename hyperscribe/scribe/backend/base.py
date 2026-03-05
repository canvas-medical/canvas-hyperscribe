from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from hyperscribe.scribe.backend.models import (
    ClinicalNote,
    NormalizedData,
    PatientContext,
    Transcript,
)


class ScribeBackend(ABC):
    """A scribe backend handles: transcription config, note generation, and structured data extraction."""

    @abstractmethod
    def get_transcription_config(self, *, user_external_id: str = "") -> dict[str, Any]:
        """Return config for the JS client: vendor, ws_url, access_token, sample_rate, encoding, etc."""
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
