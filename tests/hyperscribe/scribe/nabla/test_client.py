from unittest.mock import MagicMock, patch

import pytest
import requests

from hyperscribe.scribe.errors import (
    ScribeNormalizationError,
    ScribeNoteGenerationError,
    ScribeTranscriptionError,
)
from hyperscribe.scribe.nabla.auth import NablaAuth
from hyperscribe.scribe.nabla.client import NablaClient


def _make_client():
    auth = MagicMock(spec=NablaAuth)
    auth.base_url = "https://us.nabla.com/api/server"
    auth.get_access_token.return_value = "test-token"
    return NablaClient(auth), auth


def _mock_response(json_data, status_code=200):
    response = MagicMock()
    response.json.return_value = json_data
    response.status_code = status_code
    response.raise_for_status.return_value = None
    return response


def _mock_error_response(status_code=500):
    response = MagicMock()
    response.status_code = status_code
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    return response


def test_transcribe_sync_success():
    client, auth = _make_client()
    expected = {"items": [{"text": "hello", "speaker": "patient"}]}

    with patch("hyperscribe.scribe.nabla.client.requests.post", return_value=_mock_response(expected)) as mock_post:
        result = client.transcribe_sync(b"audio-data", {"speech_locales": "en-US"})

    assert result == expected
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "transcribe" in call_kwargs.args[0]
    assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer test-token"


def test_transcribe_sync_error():
    client, _ = _make_client()
    with patch("hyperscribe.scribe.nabla.client.requests.post", return_value=_mock_error_response(422)):
        with pytest.raises(ScribeTranscriptionError, match="Nabla transcribe failed"):
            client.transcribe_sync(b"audio", {})


def test_transcribe_async_start_success():
    client, _ = _make_client()
    expected = {"id": "job-123"}
    with patch("hyperscribe.scribe.nabla.client.requests.post", return_value=_mock_response(expected)) as mock_post:
        result = client.transcribe_async_start({"file_url": "http://example.com/audio.wav"})

    assert result == expected
    call_kwargs = mock_post.call_args
    assert "transcribe-async" in call_kwargs.args[0]
    assert call_kwargs.kwargs["json"] == {"file_url": "http://example.com/audio.wav"}


def test_transcribe_async_start_error():
    client, _ = _make_client()
    with patch("hyperscribe.scribe.nabla.client.requests.post", return_value=_mock_error_response(500)):
        with pytest.raises(ScribeTranscriptionError, match="async transcribe start failed"):
            client.transcribe_async_start({})


def test_transcribe_async_poll_success():
    client, _ = _make_client()
    expected = {"id": "job-123", "status": "succeeded", "items": []}
    with patch("hyperscribe.scribe.nabla.client.requests.get", return_value=_mock_response(expected)) as mock_get:
        result = client.transcribe_async_poll("job-123")

    assert result == expected
    assert "job-123" in mock_get.call_args.args[0]


def test_transcribe_async_poll_error():
    client, _ = _make_client()
    with patch("hyperscribe.scribe.nabla.client.requests.get", return_value=_mock_error_response(404)):
        with pytest.raises(ScribeTranscriptionError, match="async transcribe poll failed"):
            client.transcribe_async_poll("bad-id")


def test_generate_note_success():
    client, _ = _make_client()
    expected = {"title": "SOAP Note", "sections": []}
    with patch("hyperscribe.scribe.nabla.client.requests.post", return_value=_mock_response(expected)) as mock_post:
        result = client.generate_note({"transcript": {}})

    assert result == expected
    assert "generate-note" in mock_post.call_args.args[0]


def test_generate_note_error():
    client, _ = _make_client()
    with patch("hyperscribe.scribe.nabla.client.requests.post", return_value=_mock_error_response(500)):
        with pytest.raises(ScribeNoteGenerationError, match="generate note failed"):
            client.generate_note({})


def test_generate_normalized_data_success():
    client, _ = _make_client()
    expected = {"conditions": [], "observations": []}
    with patch("hyperscribe.scribe.nabla.client.requests.post", return_value=_mock_response(expected)) as mock_post:
        result = client.generate_normalized_data({"note": {}})

    assert result == expected
    assert "generate-normalized-data" in mock_post.call_args.args[0]


def test_generate_normalized_data_error():
    client, _ = _make_client()
    with patch("hyperscribe.scribe.nabla.client.requests.post", return_value=_mock_error_response(503)):
        with pytest.raises(ScribeNormalizationError, match="generate normalized data failed"):
            client.generate_normalized_data({})


def test_headers_include_bearer_token():
    client, auth = _make_client()
    auth.get_access_token.return_value = "my-token"
    headers = client._headers()
    assert headers == {"Authorization": "Bearer my-token"}
