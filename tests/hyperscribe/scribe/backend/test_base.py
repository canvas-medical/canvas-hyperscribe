from typing import Any

import pytest

from hyperscribe.scribe.backend import (
    ClinicalNote,
    NormalizedData,
    PatientContext,
    ScribeBackend,
    Transcript,
)


def test_scribe_backend_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError, match="abstract method"):
        ScribeBackend()


def test_partial_implementation_fails() -> None:
    class Partial(ScribeBackend):
        def get_transcription_config(self) -> dict[str, Any]:
            return {}

    with pytest.raises(TypeError, match="abstract method"):
        Partial()


def test_complete_implementation_works() -> None:
    class Complete(ScribeBackend):
        def get_transcription_config(self) -> dict[str, Any]:
            return {"vendor": "test", "ws_url": "wss://example.com"}

        def generate_note(
            self,
            transcript: Transcript,
            *,
            patient_context: PatientContext | None = None,
        ) -> ClinicalNote:
            return ClinicalNote(title="test")

        def generate_normalized_data(self, note: ClinicalNote) -> NormalizedData:
            return NormalizedData()

    backend = Complete()
    assert isinstance(backend, ScribeBackend)

    config = backend.get_transcription_config()
    assert isinstance(config, dict)
    assert config["vendor"] == "test"

    note = backend.generate_note(Transcript())
    assert isinstance(note, ClinicalNote)

    normalized = backend.generate_normalized_data(note)
    assert isinstance(normalized, NormalizedData)


def test_generate_note_accepts_patient_context() -> None:
    class WithContext(ScribeBackend):
        def get_transcription_config(self) -> dict[str, Any]:
            return {}

        def generate_note(
            self,
            transcript: Transcript,
            *,
            patient_context: PatientContext | None = None,
        ) -> ClinicalNote:
            return ClinicalNote(title=patient_context.name if patient_context else "none")

        def generate_normalized_data(self, note: ClinicalNote) -> NormalizedData:
            return NormalizedData()

    backend = WithContext()
    ctx = PatientContext(name="John Doe", birth_date="1980-01-01", gender="male")
    note = backend.generate_note(Transcript(), patient_context=ctx)
    assert note.title == "John Doe"
