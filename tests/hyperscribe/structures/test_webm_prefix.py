from hashlib import md5
from unittest.mock import patch, call

from hyperscribe.structures.webm_prefix import WebmPrefix


@patch.object(WebmPrefix, "decoded_prefix")
def test_add_prefix(decoded_prefix):
    tested = WebmPrefix
    decoded_prefix.side_effect = [b"thePrefix"]
    result = tested.add_prefix(b"SomeContent")
    expected = b"thePrefixSomeContent"
    assert result == expected

    calls = [call()]
    assert decoded_prefix.mock_calls == calls


def test_decoded_prefix():
    tested = WebmPrefix
    result = tested.decoded_prefix()
    expected = "8ae25a98db40517c9f2c5ccb2e066abd"
    assert md5(result).hexdigest() == expected
