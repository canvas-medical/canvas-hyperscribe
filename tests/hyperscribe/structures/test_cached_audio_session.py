from hyperscribe.structures.cached_audio_session import CachedAudioSession
from tests.helper import is_namedtuple


def test_class():
    tested = CachedAudioSession
    fields = {
        "session_id": str,
        "user_token": str,
        "logged_in_user_id": str,
    }
    assert is_namedtuple(tested, fields)
