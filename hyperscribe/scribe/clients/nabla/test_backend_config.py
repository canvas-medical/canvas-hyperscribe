"""Tests for the Nabla /config payload (KOALA-5934 capture-quality flag)."""

from unittest.mock import patch

from hyperscribe.scribe.clients.nabla.backend import NablaBackend


def test_transcription_config_defaults_echo_cancellation_true() -> None:
    """echo_cancellation defaults to True so capture behavior is unchanged."""
    with (
        patch("hyperscribe.scribe.clients.nabla.backend.NablaAuth") as mock_auth_cls,
        patch("hyperscribe.scribe.clients.nabla.backend.NablaClient"),
    ):
        auth = mock_auth_cls.return_value
        auth.base_url = "https://api.nabla.com"
        auth.get_user_tokens.return_value = ("access-tok", "refresh-tok")
        backend = NablaBackend(client_id="cid", client_secret="csecret")
        config = backend.get_transcription_config(user_external_id="u1")

    assert config["echo_cancellation"] is True
