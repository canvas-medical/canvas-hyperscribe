import json
from typing import Any

import pytest

from hyperscribe.scribe.backend import (
    ClinicalNote,
    NormalizedData,
    ScribeBackend,
    ScribeError,
    Transcript,
)
from hyperscribe.scribe.backend.registry import _REGISTRY, get_backend_from_secrets, register_backend


class _FakeBackend(ScribeBackend):
    def __init__(self, **kwargs: str) -> None:
        self.kwargs = kwargs

    def get_transcription_config(self) -> dict[str, Any]:
        return {"vendor": "fake"}

    def generate_note(self, transcript: Transcript, *, patient_context: object = None) -> ClinicalNote:
        return ClinicalNote(title="fake")

    def generate_normalized_data(self, note: ClinicalNote) -> NormalizedData:
        return NormalizedData()


def test_register_backend() -> None:
    original = dict(_REGISTRY)
    try:
        register_backend("TestVendor", _FakeBackend)
        assert _REGISTRY["testvendor"] is _FakeBackend
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(original)


def test_get_backend_from_secrets_returns_backend() -> None:
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


def test_get_backend_from_secrets_case_insensitive() -> None:
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


def test_get_backend_from_secrets_unknown_vendor() -> None:
    secrets = {
        "ScribeBackend": json.dumps({"vendor": "nonexistent"}),
    }
    with pytest.raises(ScribeError, match="Unknown scribe vendor"):
        get_backend_from_secrets(secrets)


def test_get_backend_from_secrets_missing_secret() -> None:
    with pytest.raises(ScribeError, match="Unknown scribe vendor"):
        get_backend_from_secrets({})


def test_get_backend_from_secrets_empty_vendor() -> None:
    secrets = {
        "ScribeBackend": json.dumps({"vendor": ""}),
    }
    with pytest.raises(ScribeError, match="Unknown scribe vendor"):
        get_backend_from_secrets(secrets)


def test_get_backend_from_secrets_control_characters_in_json() -> None:
    original = dict(_REGISTRY)
    try:
        register_backend("fake", _FakeBackend)
        # Simulate a secret with literal newlines inside a value (e.g. PEM key)
        raw = '{"vendor": "fake", "client_secret": "-----BEGIN KEY-----\\nABC\\n-----END KEY-----\\n"}'
        secrets = {"ScribeBackend": raw}
        backend = get_backend_from_secrets(secrets)
        assert isinstance(backend, _FakeBackend)
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(original)


def test_nabla_auto_registers() -> None:
    import hyperscribe.scribe.clients.nabla  # noqa: F401

    assert "nabla" in _REGISTRY
