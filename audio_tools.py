import sys

from hyperscribe.libraries.audio_client import AudioClient


if __name__ == "__main__":
    subdomain = sys.argv[1]
    audio_client = AudioClient()
    resp = audio_client.register_customer(subdomain)
    print(resp.status_code)
    print(resp.text)
