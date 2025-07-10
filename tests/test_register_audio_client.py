import os
import sys
import runpy
from hyperscribe.libraries.audio_client import AudioClient

class DummyResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


def test_register_audio_client(monkeypatch, capsys):
    monkeypatch.setenv("AUDIO_SERVER_URL", "https://theAudioServer.com")
    monkeypatch.setenv("AUDIO_SERVER_REGISTRATION_KEY", "theRegistrationKey")
    monkeypatch.setattr(AudioClient, '__init__', lambda self, url, key: None)
    monkeypatch.setattr(AudioClient, 'register_customer', lambda self, sd: DummyResponse(200, "OK"))
    sys.argv = ['register_audio_client.py', 'subdomain']
    runpy.run_path(os.path.join(os.path.dirname(__file__), '../register_audio_client.py'), run_name='__main__')
    output = capsys.readouterr().out.splitlines()
    assert output == ['200', 'OK']
