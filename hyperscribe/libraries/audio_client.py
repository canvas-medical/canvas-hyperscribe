import re
import requests

from base64 import b64decode
from requests import Response
from logger import log
from typing import NamedTuple

from canvas_sdk.handlers.simple_api import api
from canvas_sdk.caching.plugins import get_cache


WEBM_PREFIX_BASE64_ENCODED = (
    "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"
)


class CachedAudioSession(NamedTuple):
    session_id: str
    user_token: str
    logged_in_user_id: str


class AudioClient:
    cache = get_cache()

    def __init__(self, 
                 base_url: str, 
                 registration_key: str | None = None, 
                 instance: str | None = None,
                 instance_key: str | None = None
                 ): 
        self.base_url = base_url
        self.registration_key = registration_key
        self.instance = instance
        self.instance_key = instance_key

    def register_customer(self, subdomain: str) -> Response:
        url = f'{self.base_url}/customers'
        headers = {'Authorization': self.registration_key}
        data = {'customer_identifier': subdomain}
        return requests.post(url, headers=headers, json=data)

    def get_user_token(self, user_identifier: str) -> str:
        headers = {
            'Canvas-Customer-Identifier': self.instance,
            'Canvas-Customer-Shared-Secret': self.instance_key,
            "Content-Type": "application/json"
        }
        url = f'{self.base_url}/user-tokens'
        data = {'user_external_id': user_identifier}
        resp = requests.post(url, headers=headers, json=data)
        json_response = resp.json()
        return json_response['token']

    def create_session(self, user_token: str, meta: dict) -> str:
        headers = {
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json"
        }
        url = f'{self.base_url}/sessions'
        resp = requests.post(url, headers=headers, json={'meta': meta})
        json_response = resp.json()
        return json_response['id']

    def save_audio_chunk(self, 
                         patient_id: str, 
                         note_id: str, 
                         audio_file: api.FileFormPart
                         ) -> Response:
        match = re.search(r"chunk_(\d+)_", audio_file.filename)
        sequence_number = int(match.group(1))

        if sequence_number == 1:
            webm_bytes = audio_file.content
        else:
            # add prefix to webm content if not the first chunk
            # need this in order to enable ffmpeg conversion to mp3 on audio server
            webm_bytes = b64decode(WEBM_PREFIX_BASE64_ENCODED) + audio_file.content

        session = self.get_latest_session(patient_id, note_id)
        if not session:
            resp = Response()
            resp._content = b"Conflict: There is no audio server session for this note"
            resp.status_code = 409
            return resp

        url = f'{self.base_url}/sessions/{session.session_id}/chunks'
        headers = {"Authorization": f"Bearer {session.user_token}"}
        files = {'audio': (audio_file.filename, webm_bytes, audio_file.content_type)}
        data = {'sequence_number': sequence_number}
        
        return requests.post(url, headers=headers, files=files, data=data)

    def get_audio_chunk(self, patient_id: str, note_id: str, chunk_id: int) -> bytes:
        session = self.get_latest_session(patient_id, note_id)
        url = f'{self.base_url}/sessions/{session.session_id}/chunks'
        headers = {"Authorization": f"Bearer {session.user_token}"}
        params = {'sequence_number': chunk_id}
        resp = requests.get(url, headers=headers, params=params)
        
        if resp.status_code == 204:
            return b''
        
        s3_presigned_url = resp.json()['url']
        resp = requests.get(s3_presigned_url)
        return resp.content

    @classmethod
    def sessions_key(cls, patient_id: str, note_id: str) -> str:
        return f"'hyperscribe.sessions'.{patient_id}.{note_id}"

    @classmethod
    def get_sessions(cls, patient_id, note_id):
        key = cls.sessions_key(patient_id, note_id)
        return cls.cache.get(key, default=[])

    @classmethod
    def get_latest_session(cls, patient_id: str, note_id: str) -> CachedAudioSession | None:
        sessions = cls.get_sessions(patient_id, note_id)
        if not sessions:
            return None
        return sessions[-1]

    @classmethod
    def add_session(cls, 
                    patient_id: str, 
                    note_id: str, 
                    session_id: str, 
                    logged_in_user_id: str, 
                    user_token: str) -> None:
        sessions = cls.get_sessions(patient_id, note_id)
        new_session = CachedAudioSession(session_id, user_token, logged_in_user_id)
        sessions.append(new_session)
        key = cls.sessions_key(patient_id, note_id)
        cls.cache.set(key, sessions)
