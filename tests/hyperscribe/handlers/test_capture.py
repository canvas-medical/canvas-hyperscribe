import re
from types import SimpleNamespace
from unittest.mock import patch

from canvas_sdk.effects.simple_api import Response, HTMLResponse
from canvas_sdk.handlers.simple_api import SimpleAPI, Credentials

import hyperscribe.handlers.capture as capture
from hyperscribe.handlers.capture import CaptureView
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.audio_client import AudioClient

# Disable automatic route resolution
CaptureView._ROUTES = {}


def helper_instance():
    # Minimal fake event with method context
    event = SimpleNamespace(context={'method': 'GET'})
    secrets = {
        Constants.SECRET_API_SIGNING_KEY: 'signkey',
        Constants.SECRET_AUDIO_HOST: 'https://audio',
        Constants.SECRET_AUDIO_HOST_PRE_SHARED_KEY: 'shared',
        Constants.SECRET_AUDIO_INTERVAL: 5,
        Constants.COPILOTS_TEAM_FHIR_GROUP_ID: 'team123',
        Constants.FUMAGE_BEARER_TOKEN: 'btok',
    }
    environment = {Constants.CUSTOMER_IDENTIFIER: 'cust'}
    view = CaptureView(event, secrets, environment)
    view._path_pattern = re.compile(r".*")
    return view


def test_class():
    assert issubclass(CaptureView, SimpleAPI)


def test_constants():
    # PREFIX exists (even if None)
    assert hasattr(CaptureView, 'PREFIX')


@patch.object(Authenticator, 'check')
def test_authenticate(check):
    view = helper_instance()
    view.request = SimpleNamespace(query_params={'ts': '123', 'sig': 'abc'})
    creds = Credentials(view.request)

    # False case
    check.return_value = False
    assert view.authenticate(creds) is False
    check.assert_called_once_with(
        'signkey',
        Constants.API_SIGNED_EXPIRATION_SECONDS,
        {'ts': '123', 'sig': 'abc'}
    )
    check.reset_mock()

    # True case
    check.return_value = True
    assert view.authenticate(creds) is True
    check.assert_called_once()


def test_capture_get(monkeypatch):
    view = helper_instance()
    view.request = SimpleNamespace(
        path_params={'patient_id': 'p', 'note_id': 'n'},
        query_params={}, headers={}
    )
    # stub presigned_url and template
    urls = []
    monkeypatch.setattr(Authenticator, 'presigned_url',
                        lambda key, url, params=None: urls.append((url, params)) or 'url')
    monkeypatch.setattr(capture, 'render_to_string', lambda tmpl, ctx: '<html/>')

    result = view.capture_get()
    assert isinstance(result, list) and len(result) == 1
    resp = result[0]
    assert isinstance(resp, HTMLResponse)
    # Access .content or .body
    content = getattr(resp, 'content', None) or getattr(resp, 'body', None)
    if isinstance(content, bytes):
        content = content.decode()
    assert '<html/>' in content
    # three URLs generated
    assert len(urls) == 3
    expected_routes = [
        f"{Constants.PLUGIN_API_BASE_ROUTE}/progress",
        f"{Constants.PLUGIN_API_BASE_ROUTE}/capture/new-session/p/n",
        f"{Constants.PLUGIN_API_BASE_ROUTE}/audio/p/n",
    ]
    assert [u[0] for u in urls] == expected_routes

@patch.object(AudioClient, 'get_user_token', return_value='ut')
@patch.object(AudioClient, 'create_session', return_value='sid')
@patch.object(AudioClient, 'add_session')
@patch('hyperscribe.handlers.capture.Staff.objects.get', return_value=SimpleNamespace(id='staffid'))
def test_new_session_post(get_staff, add_sess, create_sess, get_utok, monkeypatch):
    view = helper_instance()
    view.request = SimpleNamespace(
        path_params={'patient_id': 'p', 'note_id': 'n'},
        headers={'canvas-logged-in-user-id': 'u'}
    )
    fake = SimpleNamespace(content=b'ok', status_code=201)
    monkeypatch.setattr(capture.requests, 'post', lambda url, json, headers: fake)

    result = view.new_session_post()
    assert isinstance(result, list) and len(result) == 1
    resp = result[0]
    assert isinstance(resp, Response)
    assert resp.content == b'ok'
    assert resp.status_code == 201

@patch.object(AudioClient, 'save_audio_chunk')
def test_audio_chunk_post(save_chunk):
    view = helper_instance()
    # missing file part
    view.request = SimpleNamespace(path_params={'patient_id':'p','note_id':'n'}, form_data=lambda: {})
    resp = view.audio_chunk_post()
    assert isinstance(resp, Response) and resp.status_code == 400

    # non-file part
    class Part:
        name = 'audio'
        filename = 'f'
        content = b''
        content_type = 'audio/test'
        def is_file(self): return False
    view.request = SimpleNamespace(path_params={'patient_id':'p','note_id':'n'}, form_data=lambda: {'audio': Part()})
    resp = view.audio_chunk_post()
    assert isinstance(resp, Response) and resp.status_code == 422

    # save error (returns list)
    save_chunk.return_value = SimpleNamespace(status_code=500, content=b'err')
    class PartOK(Part):
        def is_file(self): return True
    view.request = SimpleNamespace(path_params={'patient_id':'p','note_id':'n'}, form_data=lambda: {'audio': PartOK()})
    result = view.audio_chunk_post()
    assert isinstance(result, list)
    resp = result[0]
    assert resp.status_code == 500 and resp.content == b'err'

    # save success
    save_chunk.return_value = SimpleNamespace(status_code=201, content=b'')
    result = view.audio_chunk_post()
    resp = result[0]
    assert resp.status_code == 201 and resp.content == b'Audio chunk saved OK'
