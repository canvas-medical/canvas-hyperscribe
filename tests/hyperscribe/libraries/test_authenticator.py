from time import time
from unittest.mock import patch, call

from hyperscribe.libraries.authenticator import Authenticator


@patch("hyperscribe.libraries.authenticator.time", wraps=time)
def test_check(mock_time):
    def reset_mocks():
        mock_time.reset_mock()

    tested = Authenticator

    tests = [
        (
            {"ts": "1746790419", "sig": "db6ba533682736ca1937979afa2b461c49f659f73cc565e64e00771c77e8d5be"},
            60,
            True,
            True,
        ),  # good
        (
            {"ts": "1746790419", "sig": "db6ba533682736ca1937979afa2b461c49f659f73cc565e64e00771c77e8d5bx"},
            60,
            True,
            False,
        ),  # incorrect
        (
            {"ts": "1746790419", "sig": "db6ba533682736ca1937979afa2b461c49f659f73cc565e64e00771c77e8d5be"},
            59,
            True,
            False,
        ),  # too old
        ({"sig": "db6ba533682736ca1937979afa2b461c49f659f73cc565e64e00771c77e8d5be"}, 60, False, False),  # missing ts
        ({"ts": "1746790419"}, 60, False, False),  # missing sig
    ]

    secret = "theSecret"
    for idx, (params, expiration, exp_calls, expected) in enumerate(tests):
        mock_time.side_effect = [1746790478.775192]

        result = tested.check(secret, expiration, params)
        assert result is expected, f"---> {idx}"

        calls = []
        if exp_calls:
            calls = [call()]
        assert mock_time.mock_calls == calls
        reset_mocks()


@patch("hyperscribe.libraries.authenticator.time", wraps=time)
def test_presigned_url(mock_time):
    def reset_mocks():
        mock_time.reset_mock()

    tested = Authenticator
    tests = [
        (
            "theSecret",
            "theUrl",
            {"param": "value"},
            1746790478.775192,
            "theUrl?param=value&ts=1746790478&sig=6b2c76bb73f5eaa97c96debb431f63eefdd6297e9be52c08a7ba0871237a0ac2",
        ),
        (
            "TheSecret",
            "theUrl",
            {"param": "value"},
            1746790478.775192,
            "theUrl?param=value&ts=1746790478&sig=fb817445d7b5c88aa8a672b93f48010a3f83305943dbe5db49ebf5876b2cb8e2",
        ),
        (
            "theSecret",
            "TheUrl",
            {"param": "value"},
            1746790478.775192,
            "TheUrl?param=value&ts=1746790478&sig=6b2c76bb73f5eaa97c96debb431f63eefdd6297e9be52c08a7ba0871237a0ac2",
        ),
        (
            "theSecret",
            "theUrl",
            {"param": "Value"},
            1746790478.775192,
            "theUrl?param=Value&ts=1746790478&sig=6b2c76bb73f5eaa97c96debb431f63eefdd6297e9be52c08a7ba0871237a0ac2",
        ),
        (
            "theSecret",
            "theUrl",
            {"param": "value"},
            1746790478.775199,
            "theUrl?param=value&ts=1746790478&sig=6b2c76bb73f5eaa97c96debb431f63eefdd6297e9be52c08a7ba0871237a0ac2",
        ),
    ]
    for idx, (secret, url, params, now, expected) in enumerate(tests):
        mock_time.side_effect = [now]
        result = tested.presigned_url(secret, url, params)
        assert result == expected, f"---> {idx}"
        calls = [call()]
        assert mock_time.mock_calls == calls
        reset_mocks()


@patch.object(Authenticator, "presigned_url")
def test_presigned_url_no_params(presigned_url):
    def reset_mock():
        presigned_url.reset_mock()

    tested = Authenticator
    presigned_url.side_effect = ["theUrl"]
    result = tested.presigned_url_no_params("theSecret", "theUrl")
    assert result == "theUrl"
    calls = [call("theSecret", "theUrl", {})]
    assert presigned_url.mock_calls == calls
    reset_mock()
