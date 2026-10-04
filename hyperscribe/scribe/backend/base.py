from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from hyperscribe.scribe.backend.errors import ScribeError
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

    def get_dictation_config(self, *, user_external_id: str = "") -> dict[str, Any]:
        """Return dictation config for the JS client: ws_url, access_token, dictation_locale, punctuation_mode.

        Dictation (talking into a single field post-generation) is an *optional*
        capability. Unlike ``get_transcription_config`` — which is abstract, so
        every scribe backend must support ambient transcription — a backend that
        cannot dictate simply inherits this default. It raises to signal the
        ``/dictation-config`` endpoint that dictation is unsupported.
        """
        raise ScribeError("This scribe backend does not support dictation")

    @abstractmethod
    def generate_note(
        self,
        transcript: Transcript,
        *,
        patient_context: PatientContext | None = None,
        visit_template_name: str = "",
    ) -> ClinicalNote: ...

    @abstractmethod
    def generate_normalized_data(self, note: ClinicalNote) -> NormalizedData: ...
