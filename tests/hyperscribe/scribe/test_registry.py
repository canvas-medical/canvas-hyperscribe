import json

import pytest

from hyperscribe.scribe.base import ScribeBackend
from hyperscribe.scribe.errors import ScribeError
from hyperscribe.scribe.models import (
    AsyncJob,
    ClinicalNote,
    NormalizedData,
    Transcript,
    TranscriptionStatus,
)
from hyperscribe.scribe.registry import _REGISTRY, get_backend_from_secrets, register_backend


class _FakeBackend(ScribeBackend):
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def transcribe(self, audio, *, speech_locales):
        return Transcript()

    def transcribe_async_start(self, file_url, *, speech_locales):
        return "job-1"

    def transcribe_async_poll(self, job_id):
        return AsyncJob(id=job_id, status=TranscriptionStatus.ONGOING)

    def generate_note(self, transcript, *, template, locale, patient_context=None):
        return ClinicalNote(title="fake")

    def generate_normalized_data(self, note):
        return NormalizedData()


def test_register_backend():
    original = dict(_REGISTRY)
    try:
        register_backend("TestVendor", _FakeBackend)
        assert _REGISTRY["testvendor"] is _FakeBackend
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(original)


def test_get_backend_from_secrets_returns_backend():
    original = dict(_REGISTRY)
    try:
        register_backend("fake", _FakeBackend)
        secrets = {
            "ScribeBackend": json.dumps({"vendor": "fake", "region": "us", "api_key": "123"}),
        }
        backend = get_backend_from_secrets(secrets)
        assert isinstance(backend, _FakeBackend)
        assert backend.kwargs == {"region": "us", "api_key": "123"}
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(original)


def test_get_backend_from_secrets_case_insensitive():
    original = dict(_REGISTRY)
    try:
        register_backend("fake", _FakeBackend)
        secrets = {
            "ScribeBackend": json.dumps({"vendor": "Fake"}),
        }
        backend = get_backend_from_secrets(secrets)
        assert isinstance(backend, _FakeBackend)
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(original)


def test_get_backend_from_secrets_unknown_vendor():
    secrets = {
        "ScribeBackend": json.dumps({"vendor": "nonexistent"}),
    }
    with pytest.raises(ScribeError, match="Unknown scribe vendor"):
        get_backend_from_secrets(secrets)


def test_get_backend_from_secrets_missing_secret():
    with pytest.raises(ScribeError, match="Unknown scribe vendor"):
        get_backend_from_secrets({})


def test_get_backend_from_secrets_empty_vendor():
    secrets = {
        "ScribeBackend": json.dumps({"vendor": ""}),
    }
    with pytest.raises(ScribeError, match="Unknown scribe vendor"):
        get_backend_from_secrets(secrets)


def test_nabla_auto_registers():
    import hyperscribe.scribe.nabla  # noqa: F401

    assert "nabla" in _REGISTRY
