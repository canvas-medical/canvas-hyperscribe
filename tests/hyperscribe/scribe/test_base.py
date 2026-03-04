import pytest

from hyperscribe.scribe.base import ScribeBackend
from hyperscribe.scribe.models import (
    AsyncJob,
    ClinicalNote,
    NormalizedData,
    PatientContext,
    Transcript,
    TranscriptionStatus,
)


def test_scribe_backend_cannot_be_instantiated():
    with pytest.raises(TypeError, match="abstract method"):
        ScribeBackend()


def test_partial_implementation_fails():
    class Partial(ScribeBackend):
        def transcribe(self, audio):
            return Transcript()

    with pytest.raises(TypeError, match="abstract method"):
        Partial()


def test_complete_implementation_works():
    class Complete(ScribeBackend):
        def transcribe(self, audio):
            return Transcript()

        def transcribe_async_start(self, file_url):
            return "job-1"

        def transcribe_async_poll(self, job_id):
            return AsyncJob(id=job_id, status=TranscriptionStatus.ONGOING)

        def generate_note(self, transcript, *, patient_context=None):
            return ClinicalNote(title="test")

        def generate_normalized_data(self, note):
            return NormalizedData()

    backend = Complete()
    assert isinstance(backend, ScribeBackend)

    result = backend.transcribe(b"audio")
    assert isinstance(result, Transcript)

    job_id = backend.transcribe_async_start("http://example.com/audio.wav")
    assert job_id == "job-1"

    poll = backend.transcribe_async_poll("job-1")
    assert isinstance(poll, AsyncJob)

    note = backend.generate_note(Transcript())
    assert isinstance(note, ClinicalNote)

    normalized = backend.generate_normalized_data(note)
    assert isinstance(normalized, NormalizedData)


def test_generate_note_accepts_patient_context():
    class WithContext(ScribeBackend):
        def transcribe(self, audio):
            return Transcript()

        def transcribe_async_start(self, file_url):
            return "job-1"

        def transcribe_async_poll(self, job_id):
            return AsyncJob(id=job_id, status=TranscriptionStatus.ONGOING)

        def generate_note(self, transcript, *, patient_context=None):
            return ClinicalNote(title=patient_context.name if patient_context else "none")

        def generate_normalized_data(self, note):
            return NormalizedData()

    backend = WithContext()
    ctx = PatientContext(name="John Doe", birth_date="1980-01-01", gender="male")
    note = backend.generate_note(Transcript(), patient_context=ctx)
    assert note.title == "John Doe"
