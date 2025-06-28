import os
import sys

from hyperscribe.libraries.audio_client import AudioClient


if __name__ == "__main__":
    subdomain = sys.argv[1]
    base_url = os.getenv('AUDIO_SERVER_URL').rstrip('/')
    registration_key = os.getenv('AUDIO_SERVER_REGISTRATION_KEY')
    audio_client = AudioClient(base_url, registration_key)
    resp = audio_client.register_customer(subdomain)
    print(resp.status_code)
    print(resp.text)
