import os
import requests

from requests import Response


class AudioClient:
    def __init__(self):
        self.base_url = os.getenv('AUDIO_SERVER_URL').rstrip('/')
        self.registration_key = os.getenv('AUDIO_SERVER_REGISTRATION_KEY')

    def register_customer(self, subdomain: str) -> Response:
        url = f'{self.base_url}/customers'
        headers = {'Authorization': self.registration_key}
        data = {'customer_identifier': subdomain}
        return requests.post(url, headers=headers, json=data)

    def get_user_token(self, customer_subdomain: str, customer_secret: str, 
                       user_identifier: str) -> Response:
        headers = {
            'Canvas-Customer-Identifier': customer_subdomain,
            'Canvas-Customer-Shared-Secret': customer_secret
        }
        url = f'{self.base_url}/user-tokens'
        data = {'user_external_id': user_identifier}
        return requests.post(url, headers=headers, json=data)

    def create_session(self):
        pass

    def save_audio_chunk(self):
        pass

    def get_audio_chunk_by_sequence_number(self):
        pass

    def get_audio_chunk_by_chunk_id(self):
        pass
