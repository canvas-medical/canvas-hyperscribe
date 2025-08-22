from hashlib import md5
from unittest import mock
from unittest.mock import call, patch

import pytest

from hyperscribe.libraries.audio_client import AudioClient, CachedAudioSession, Response


class MockAudioFile:
    filename = "chunk_002_test.webm"
    content = b"raw-audio-bytes"
    content_type = "audio/webm"


@pytest.fixture
def the_audio_file() -> MockAudioFile:
    return MockAudioFile()


@pytest.fixture
def the_session() -> CachedAudioSession:
    return CachedAudioSession("theSessionId", "theUserToken", "theLoggedInUserId")


@pytest.fixture
def the_client() -> AudioClient:
    return AudioClient(
        base_url="https://theAudioServer.com",
        registration_key="theRegKey",
        instance="theInstance",
        instance_key="theSharedSecret",
    )


def test_webm_prefix():
    assert md5(AudioClient.WEBM_PREFIX).hexdigest() == "8ae25a98db40517c9f2c5ccb2e066abd"


def test___eq__():
    one_client = AudioClient(
        base_url="https://theAudioServer.com",
        registration_key="theRegKey",
        instance="theInstance",
        instance_key="theSharedSecret",
    )
    another_client = AudioClient(
        base_url="https://theAudioServer.com",
        registration_key="theRegKey",
        instance="theInstance",
        instance_key="theSharedSecret",
    )
    assert one_client is not another_client
    assert one_client == another_client


def test___repr__(the_client):
    expected = (
        f"AudioClient(base_url='{the_client.base_url}', registration_key='{the_client.registration_key}', "
        f"instance='{the_client.instance}', instance_key='{the_client.instance_key}'"
    )
    result = str(the_client)
    assert result == expected

    the_client.registration_key = None
    expected_with_none = (
        f"AudioClient(base_url='{the_client.base_url}', registration_key={the_client.registration_key}, "
        f"instance='{the_client.instance}', instance_key='{the_client.instance_key}'"
    )
    result_with_none = str(the_client)
    assert result_with_none == expected_with_none


def test_for_registration():
    tested = AudioClient
    result = tested.for_registration("theUrl", "theRegistrationKey")
    assert isinstance(result, AudioClient)
    assert result.base_url == "theUrl"
    assert result.registration_key == "theRegistrationKey"
    assert result.instance is None
    assert result.instance_key is None


def test_for_operation():
    tested = AudioClient
    result = tested.for_operation("theUrl", "theInstance", "theInstanceKey")
    assert isinstance(result, AudioClient)
    assert result.base_url == "theUrl"
    assert result.registration_key is None
    assert result.instance == "theInstance"
    assert result.instance_key == "theInstanceKey"


def test_register_customer(the_client):
    with mock.patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 201
        resp = the_client.register_customer("test-sub")
        assert resp.status_code == 201
        assert mock_post.call_args[1]["json"] == {"customer_identifier": "test-sub"}
        assert len(mock_post.mock_calls) == 1


def test_get_user_token(the_client):
    with mock.patch("requests.post") as mock_post:
        mock_post.return_value.json.return_value = {"token": "abc123"}
        token = the_client.get_user_token("user1")
        url = f"{the_client.base_url}/user-tokens"
        headers = {
            "Canvas-Customer-Identifier": the_client.instance,
            "Canvas-Customer-Shared-Secret": the_client.instance_key,
            "Content-Type": "application/json",
        }
        data = {"user_external_id": "user1"}
        assert mock_post.mock_calls == [
            mock.call(url, headers=headers, json=data),
            mock.call().json(),
        ]
        assert token == "abc123"


def test_create_session(the_client):
    with mock.patch("requests.post") as mock_post:
        mock_post.return_value.json.return_value = {"id": "sess123"}
        session_id = the_client.create_session("token123", {"meta": "data"})
        assert session_id == "sess123"


def test_save_audio_chunk__all_good(the_client, the_audio_file, the_session):
    with (
        mock.patch.object(AudioClient, "get_latest_session", return_value=the_session),
        mock.patch("requests.post") as mock_post,
    ):
        mock_response = Response()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        resp = the_client.save_audio_chunk("thePatientKey", "theNoteId", the_audio_file)

        assert resp.status_code == 200
        args, kwargs = mock_post.call_args
        assert args[0] == "https://theAudioServer.com/sessions/theSessionId/chunks"
        assert kwargs["headers"]["Authorization"] == f"Bearer {the_session.user_token}"
        assert kwargs["data"]["sequence_number"] == 2
        assert "audio" in kwargs["files"]


def test_save_audio_chunk__first_chunk_no_prefix(the_client, the_session):
    class DummyFile:
        filename = "chunk_001_test.webm"
        content = b"raw-audio-bytes"
        content_type = "audio/webm"

    dummy_file = DummyFile()

    with (
        mock.patch.object(AudioClient, "get_latest_session", return_value=the_session),
        mock.patch("requests.post") as mock_post,
    ):
        mock_response = Response()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        resp = the_client.save_audio_chunk("thePatientKey", "theNoteId", dummy_file)

        assert resp.status_code == 200
        args, kwargs = mock_post.call_args
        file_tuple = kwargs["files"]["audio"]

        # Confirm it's not prefixed
        assert file_tuple[1] == b"raw-audio-bytes"
        assert kwargs["data"]["sequence_number"] == 1


def test_save_audio_chunk__without_session(the_client, the_audio_file):
    with mock.patch.object(AudioClient, "get_latest_session", return_value=None):
        resp = the_client.save_audio_chunk("thePatientKey", "theNoteId", the_audio_file)

        assert resp.status_code == 409
        assert b"Conflict" in resp.content


def test_save_audio_chunk__invalid_name(the_client, the_audio_file):
    with pytest.raises(ValueError) as e:
        the_audio_file.filename = "part_001_test.mp3"
        _ = the_client.save_audio_chunk("thePatientKey", "theNoteId", the_audio_file)
    exp_error = "Invalid audio filename format: part_001_test.mp3"
    assert str(e.value) == exp_error


def test_get_audio_chunk__success(the_client, the_session):
    with (
        mock.patch.object(AudioClient, "get_latest_session", return_value=the_session),
        mock.patch("requests.get") as mock_get,
    ):
        # First call returns JSON with URL, second call returns content
        mock_get.side_effect = [
            mock.Mock(status_code=200, json=mock.Mock(return_value={"url": "https://s3.com/fake"})),
            mock.Mock(status_code=200, content=b"audio-bytes"),
        ]

        content = the_client.get_audio_chunk("thePatientKey", "theNoteId", 3)
        assert content == b"audio-bytes"
        assert mock_get.call_count == 2


def test_get_audio_chunk__empty_204(the_client, the_session):
    with (
        mock.patch.object(AudioClient, "get_latest_session", return_value=the_session),
        mock.patch("requests.get") as mock_get,
    ):
        mock_get.return_value.status_code = 204
        content = the_client.get_audio_chunk("thePatientKey", "theNoteId", 3)
        assert content == b""


def test_get_audio_chunk__no_session(the_client, the_session):
    with mock.patch.object(AudioClient, "get_latest_session", return_value=None):
        with pytest.raises(ValueError) as e:
            _ = the_client.get_audio_chunk("thePatientKey", "theNoteId", 3)
        exp_error = "No audio session found for patient thePatientKey, note theNoteId"
        assert str(e.value) == exp_error


def test_sessions_key():
    assert AudioClient.sessions_key("thePatientId", "theNoteId") == "hyperscribe.sessions.thePatientId.theNoteId"


def test_get_sessions(the_session: CachedAudioSession):
    with mock.patch("hyperscribe.libraries.audio_client.get_cache") as mock_cache:
        expected = [the_session]
        mock_cache.return_value.get.side_effect = [expected]

        result = AudioClient.get_sessions("pat123", "note456")

        assert result == expected
        calls = [call(), call().get("hyperscribe.sessions.pat123.note456", default=[])]
        assert mock_cache.mock_calls == calls


def test_get_latest_session(the_session: CachedAudioSession):
    with mock.patch("hyperscribe.libraries.audio_client.get_cache") as mock_cache:
        expected = [the_session]
        mock_cache.return_value.get.side_effect = [expected]

        result = AudioClient.get_latest_session("pat123", "note456")

        assert result == the_session
        calls = [call(), call().get("hyperscribe.sessions.pat123.note456", default=[])]
        assert mock_cache.mock_calls == calls


def test_get_latest_session__missing(the_session: CachedAudioSession):
    with mock.patch("hyperscribe.libraries.audio_client.get_cache") as mock_cache:
        mock_cache.return_value.get.side_effect = [None]

        result = AudioClient.get_latest_session("pat123", "note456")

        assert result is None
        calls = [call(), call().get("hyperscribe.sessions.pat123.note456", default=[])]
        assert mock_cache.mock_calls == calls


@patch("hyperscribe.libraries.audio_client.get_cache")
@patch("hyperscribe.libraries.audio_client.AudioClient.get_sessions")
def test_add_session(get_sessions, get_cache, the_session):
    def reset_mocks():
        get_sessions.reset_mock()
        get_cache.reset_mock()

    tested = AudioClient

    get_sessions.side_effect = [[]]

    tested.add_session(
        "thePatientKey",
        "theNoteId",
        the_session.session_id,
        the_session.logged_in_user_id,
        the_session.user_token,
    )

    calls = [call("thePatientKey", "theNoteId")]
    assert get_sessions.mock_calls == calls
    calls = [
        call(),
        call().set("hyperscribe.sessions.thePatientKey.theNoteId", [the_session]),
    ]
    assert get_cache.mock_calls == calls
    reset_mocks()
