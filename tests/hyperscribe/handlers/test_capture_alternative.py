import pytest
from http import HTTPStatus
from types import SimpleNamespace
from hyperscribe.handlers import capture
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.audio_client import AudioClient
from canvas_sdk.effects.simple_api import Response, HTMLResponse

# Disable route matching in BaseHandler to simplify instantiation
capture.CaptureView._ROUTES = {}

@pytest.fixture
def view():
    # Instantiate with dummy event to satisfy BaseHandler
    event = SimpleNamespace(context={'method':'GET'})
    v = capture.CaptureView(event)
    v.secrets = {
        Constants.SECRET_API_SIGNING_KEY: 'signkey',
        Constants.SECRET_AUDIO_HOST: 'https://audio',
        Constants.SECRET_AUDIO_HOST_PRE_SHARED_KEY: 'shared',
        Constants.SECRET_AUDIO_INTERVAL: 5,
        Constants.COPILOTS_TEAM_FHIR_GROUP_ID: 'team123',
        Constants.FUMAGE_BEARER_TOKEN: 'ftoken',
    }
    v.environment = {Constants.CUSTOMER_IDENTIFIER: 'cust'}
    return v


def make_request(path_params=None, query_params=None, headers=None, form_data=None):
    return SimpleNamespace(
        path_params=path_params or {},
        query_params=query_params or {},
        headers=headers or {},
        form_data=lambda: form_data or {},
    )


def unwrap(result):
    return result[0] if isinstance(result, list) else result


def test_authenticate(monkeypatch, view):
    view.request = make_request(query_params={'ts': '1', 'sig': 'abc'})
    monkeypatch.setattr(Authenticator, 'check', lambda secret, exp, params: True)
    assert view.authenticate(None) is True


def test_capture_get_renders_html(monkeypatch, view):
    view.request = make_request(path_params={'patient_id': 'p', 'note_id': 'n'})
    monkeypatch.setattr(Authenticator, 'presigned_url', lambda s, url, params=None: 'url')
    monkeypatch.setattr(capture, 'render_to_string', lambda tmpl, ctx: '<html>')
    resp = unwrap(view.capture_get())
    assert resp.status_code == HTTPStatus.OK
    content = getattr(resp, 'content', None) or getattr(resp, 'body', None)
    if isinstance(content, bytes):
        content = content.decode()
    assert '<html>' in content


def test_new_session_post(monkeypatch, view):
    view.request = make_request(
        path_params={'patient_id': 'p', 'note_id': 'n'},
        headers={'canvas-logged-in-user-id': 'u'}
    )
    monkeypatch.setattr(AudioClient, 'get_user_token', lambda self, uid: 'ut')
    monkeypatch.setattr(AudioClient, 'create_session', lambda self, ut, meta: 'sid')
    monkeypatch.setattr(AudioClient, 'add_session', lambda self, p, n, s, uid, ut: None)
    monkeypatch.setattr(capture.Staff.objects, 'get', lambda dbid: SimpleNamespace(id='staff'))
    fake_resp = SimpleNamespace(content=b'ok', status_code=201)
    monkeypatch.setattr(capture.requests, 'post', lambda url, json, headers: fake_resp)
    resp = unwrap(view.new_session_post())
    assert resp.status_code == 201
    assert resp.content == b'ok'


def test_audio_chunk_post_various(monkeypatch, view):
    # Missing audio part -> direct Response
    view.request = make_request(path_params={'patient_id': 'p', 'note_id': 'n'}, form_data={})
    resp = unwrap(view.audio_chunk_post())
    assert isinstance(resp, Response)
    assert resp.status_code == 400

    # Non-file part -> direct Response
    class Part:
        def __init__(self):
            self.name = 'audio'
            self.filename = 'f'
            self.content = b''
            self.content_type = 'audio/test'
        def is_file(self):
            return False
    view.request = make_request(path_params={'patient_id': 'p', 'note_id': 'n'}, form_data={'audio': Part()})
    resp = unwrap(view.audio_chunk_post())
    assert isinstance(resp, Response)
    assert resp.status_code == 422

    # Save error -> list Response
    class RespErr:
        status_code = 500
        content = b'err'
    monkeypatch.setattr(AudioClient, 'save_audio_chunk', lambda self, p, n, f: RespErr())
    class PartOK(Part):
        def is_file(self):
            return True
    view.request = make_request(path_params={'patient_id': 'p', 'note_id': 'n'}, form_data={'audio': PartOK()})
    resp = unwrap(view.audio_chunk_post())
    assert resp.status_code == 500

    # Save success -> list Response
    class RespOK:
        status_code = 201
        content = b''
    monkeypatch.setattr(AudioClient, 'save_audio_chunk', lambda self, p, n, f: RespOK())
    view.request = make_request(path_params={'patient_id': 'p', 'note_id': 'n'}, form_data={'audio': PartOK()})
    resp = unwrap(view.audio_chunk_post())
    assert resp.status_code == 201
    assert resp.content == b'Audio chunk saved OK'
