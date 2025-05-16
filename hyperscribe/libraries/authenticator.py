from hashlib import sha256
from time import time
from urllib.parse import urlencode


class Authenticator:
    @classmethod
    def check(cls, secret: str, expiration_seconds: int, params: dict) -> bool:
        if not ("ts" in params and "sig" in params):
            return False

        timestamp = int(params["ts"])
        if (time() - timestamp) > expiration_seconds:
            return False

        hash_arg = f"{timestamp}{secret}"
        internal_sig = sha256(hash_arg.encode('utf-8')).hexdigest()
        request_sig = params["sig"]

        return bool(request_sig == internal_sig)

    @classmethod
    def presigned_url(cls, secret: str, url: str, params: dict) -> str:
        timestamp = str(int(time()))
        hash_arg = f"{timestamp}{secret}"
        request_sig = sha256(hash_arg.encode('utf-8')).hexdigest()
        return f'{url}?{urlencode(params | {"ts": timestamp, "sig": request_sig})}'
