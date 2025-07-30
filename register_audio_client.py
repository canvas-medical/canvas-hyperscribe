import os
import sys

from hyperscribe.libraries.audio_client import AudioClient


if __name__ == "__main__":
    subdomain = sys.argv[1]

    base_url = os.getenv("AUDIO_SERVER_URL")
    if base_url is None:
        raise EnvironmentError("You must set the AUDIO_SERVER_URL environment variable.")

    registration_key = os.getenv("AUDIO_SERVER_REGISTRATION_KEY")
    if registration_key is None:
        raise EnvironmentError("You must set the AUDIO_SERVER_REGISTRATION_KEY environment variable.")

    base_url = str(base_url).rstrip("/")
    registration_key = str(registration_key).strip()

    audio_client = AudioClient.for_registration(base_url, registration_key)
    resp = audio_client.register_customer(subdomain)

    print(resp.status_code)
    print(resp.text)
