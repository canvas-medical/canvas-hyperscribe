import pytest

from hyperscribe.scribe.backend import (
    ScribeAuthError,
    ScribeError,
    ScribeNormalizationError,
    ScribeNoteGenerationError,
    ScribeTranscriptionError,
)


def test_scribe_error_message_and_status_code():
    error = ScribeError("something broke", status_code=500)
    assert str(error) == "something broke"
    assert error.status_code == 500


def test_scribe_error_default_status_code():
    error = ScribeError("no code")
    assert error.status_code == 0


def test_scribe_error_is_exception():
    assert issubclass(ScribeError, Exception)


def test_scribe_auth_error_inherits():
    error = ScribeAuthError("auth failed", status_code=401)
    assert isinstance(error, ScribeError)
    assert str(error) == "auth failed"
    assert error.status_code == 401


def test_scribe_transcription_error_inherits():
    error = ScribeTranscriptionError("transcribe failed", status_code=422)
    assert isinstance(error, ScribeError)
    assert error.status_code == 422


def test_scribe_note_generation_error_inherits():
    error = ScribeNoteGenerationError("note failed")
    assert isinstance(error, ScribeError)
    assert error.status_code == 0


def test_scribe_normalization_error_inherits():
    error = ScribeNormalizationError("normalize failed", status_code=503)
    assert isinstance(error, ScribeError)
    assert error.status_code == 503


def test_all_errors_can_be_caught_as_scribe_error():
    errors = [
        ScribeAuthError("a"),
        ScribeTranscriptionError("b"),
        ScribeNoteGenerationError("c"),
        ScribeNormalizationError("d"),
    ]
    for error in errors:
        with pytest.raises(ScribeError):
            raise error
