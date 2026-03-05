import pytest

from hyperscribe.scribe.backend import (
    ClinicalNote,
    NormalizedData,
    PatientContext,
    ScribeBackend,
    Transcript,
    TranscriptItem,
)


def test_scribe_backend_cannot_be_instantiated():
    with pytest.raises(TypeError, match="abstract method"):
        ScribeBackend()


def test_partial_implementation_fails():
    class Partial(ScribeBackend):
        def start_session(self) -> None:
            pass

    with pytest.raises(TypeError, match="abstract method"):
        Partial()


def test_complete_implementation_works():
    class Complete(ScribeBackend):
        def start_session(self) -> None:
            pass

        def send_audio(self, audio: bytes) -> None:
            pass

        def get_transcript_updates(self) -> list[TranscriptItem]:
            return []

        def end_session(self) -> Transcript:
            return Transcript()

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

    backend.start_session()
    backend.send_audio(b"audio")
    updates = backend.get_transcript_updates()
    assert updates == []

    transcript = backend.end_session()
    assert isinstance(transcript, Transcript)

    note = backend.generate_note(Transcript())
    assert isinstance(note, ClinicalNote)

    normalized = backend.generate_normalized_data(note)
    assert isinstance(normalized, NormalizedData)


def test_generate_note_accepts_patient_context():
    class WithContext(ScribeBackend):
        def start_session(self) -> None:
            pass

        def send_audio(self, audio: bytes) -> None:
            pass

        def get_transcript_updates(self) -> list[TranscriptItem]:
            return []

        def end_session(self) -> Transcript:
            return Transcript()

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
