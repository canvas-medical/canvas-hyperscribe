import pytest
from hashlib import md5
from unittest import mock
from hyperscribe.libraries.audio_client import AudioClient, CachedAudioSession, Response


AUDIO_CLIENT_IMPORT_PATH = 'hyperscribe.libraries.audio_client.AudioClient'


class MockAudioFile:
    filename = "chunk_002_test.webm"
    content = b"raw-audio-bytes"
    content_type = "audio/webm"


@pytest.fixture
def the_audio_file() -> MockAudioFile:
    return MockAudioFile()


@pytest.fixture
def the_session() -> CachedAudioSession:
    return CachedAudioSession('theSessionId', 'theUserToken', 'theLoggedInUserId')


@pytest.fixture
def the_client() -> AudioClient:
    return AudioClient(
        base_url='https://theAudioServer.com', 
        registration_key='theRegKey', 
        instance='theInstance',
        instance_key='theSharedSecret'
    )


def test_webm_prefix():
    assert md5(AudioClient.WEBM_PREFIX).hexdigest() == '8ae25a98db40517c9f2c5ccb2e066abd'


def test___eq__():
    one_client = AudioClient(
        base_url='https://theAudioServer.com', 
        registration_key='theRegKey', 
        instance='theInstance',
        instance_key='theSharedSecret'
    )
    another_client = AudioClient(
        base_url='https://theAudioServer.com', 
        registration_key='theRegKey', 
        instance='theInstance',
        instance_key='theSharedSecret'
    )
    assert one_client is not another_client
    assert one_client == another_client


def test___repr__(the_client):
    expected = (f"AudioClient(base_url='{the_client.base_url}', registration_key='{the_client.registration_key}', "
                f"instance='{the_client.instance}', instance_key='{the_client.instance_key}'")
    result = str(the_client)
    assert result == expected
    
    the_client.registration_key = None
    expected_with_none = (f"AudioClient(base_url='{the_client.base_url}', registration_key={the_client.registration_key}, "
                f"instance='{the_client.instance}', instance_key='{the_client.instance_key}'")
    result_with_none = str(the_client)
    assert result_with_none == expected_with_none
    


def test_register_customer(the_client):
    with mock.patch('requests.post') as mock_post:
        mock_post.return_value.status_code = 201
        resp = the_client.register_customer('test-sub')
        assert resp.status_code == 201
        assert mock_post.call_args[1]['json'] == {'customer_identifier': 'test-sub'}


def test_get_user_token(the_client):
    with mock.patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = {'token': 'abc123'}
        token = the_client.get_user_token('user1')
        assert token == 'abc123'


def test_create_session(the_client):
    with mock.patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = {'id': 'sess123'}
        session_id = the_client.create_session('token123', {'meta': 'data'})
        assert session_id == 'sess123'


def test_save_audio_chunk(the_client, the_audio_file, the_session):
    with mock.patch.object(AudioClient, "get_latest_session", return_value=the_session), \
         mock.patch("requests.post") as mock_post:
        
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


def test_save_audio_chunk_first_chunk_no_prefix(the_client, the_session):
    class DummyFile:
        filename = "chunk_001_test.webm"
        content = b"raw-audio-bytes"
        content_type = "audio/webm"

    dummy_file = DummyFile()

    with mock.patch.object(AudioClient, "get_latest_session", return_value=the_session), \
         mock.patch("requests.post") as mock_post:
        
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


def test_save_audio_chunk_without_session(the_client, the_audio_file):
    with mock.patch.object(AudioClient, "get_latest_session", return_value=None):
        resp = the_client.save_audio_chunk("thePatientKey", "theNoteId", the_audio_file)

        assert resp.status_code == 409
        assert b"Conflict" in resp.content


def test_get_audio_chunk_success(the_client, the_session):
    with mock.patch.object(AudioClient, "get_latest_session", return_value=the_session), \
         mock.patch("requests.get") as mock_get:

        # First call returns JSON with URL, second call returns content
        mock_get.side_effect = [
            mock.Mock(status_code=200, json=mock.Mock(return_value={"url": "https://s3.com/fake"})),
            mock.Mock(status_code=200, content=b"audio-bytes")
        ]

        content = the_client.get_audio_chunk("thePatientKey", "theNoteId", 3)
        assert content == b"audio-bytes"
        assert mock_get.call_count == 2


def test_get_audio_chunk_empty_204(the_client, the_session):
    with mock.patch.object(AudioClient, "get_latest_session", return_value=the_session), \
         mock.patch("requests.get") as mock_get:

        mock_get.return_value.status_code = 204
        content = the_client.get_audio_chunk("thePatientKey", "theNoteId", 3)
        assert content == b""


def test_sessions_key():
    assert AudioClient.sessions_key('thePatientId', 'theNoteId') == 'hyperscribe.sessions.thePatientId.theNoteId'


def test_get_sessions(the_session: CachedAudioSession):
    patient_id = "pat123"
    note_id = "note456"
    expected_key = f"hyperscribe.sessions.{patient_id}.{note_id}"
    expected_sessions = [the_session]

    with mock.patch.object(AudioClient, "cache") as mock_cache:
        mock_cache.get.return_value = expected_sessions
        sessions = AudioClient.get_sessions(patient_id, note_id)
        mock_cache.get.assert_called_once_with(expected_key, default=[])
        assert sessions == expected_sessions


def test_get_latest_session(the_session: CachedAudioSession):
    patient_id = "pat123"
    note_id = "note456"
    expected_key = f"hyperscribe.sessions.{patient_id}.{note_id}"
    expected_sessions = [the_session]

    with mock.patch.object(AudioClient, "cache") as mock_cache:
        mock_cache.get.return_value = expected_sessions
        latest_session = AudioClient.get_latest_session(patient_id, note_id)
        mock_cache.get.assert_called_once_with(expected_key, default=[])
        assert latest_session == the_session


def test_get_latest_session_missing(the_session: CachedAudioSession):
    with mock.patch.object(AudioClient, "cache") as mock_cache:
        mock_cache.get.return_value = None
        latest_session = AudioClient.get_latest_session("thePatientId", "theNoteId")
        mock_cache.get.assert_called_once_with(
            "hyperscribe.sessions.thePatientId.theNoteId", default=[])
        assert latest_session is None


def test_add_session(the_session):
    with mock.patch(f'{AUDIO_CLIENT_IMPORT_PATH}.get_sessions', return_value=[]), \
         mock.patch(f'{AUDIO_CLIENT_IMPORT_PATH}.cache') as mock_cache:
        AudioClient.add_session('thePatientKey', 'theNoteId', the_session.session_id, 
                                the_session.logged_in_user_id, the_session.user_token)
        key = AudioClient.sessions_key('thePatientKey', 'theNoteId')
        mock_cache.set.assert_called_once_with(key, [the_session])
