from typing import NamedTuple


class CachedAudioSession(NamedTuple):
    session_id: str
    user_token: str
    logged_in_user_id: str
