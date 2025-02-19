import json
from unittest.mock import patch, call

from logger import log

from commander.protocols.llms.llm_google import LlmGoogle
from commander.protocols.structures.json_extract import JsonExtract


def test_to_dict():
    tested = LlmGoogle("googleKey", "theModel")
    tested.system_prompt = ["line 1", "line 2", "line 3"]
    tested.user_prompt = ["line 4", "line 5", "line 6"]
    expected = {
        'contents': [
            {
                "role": "user",
                "parts": [
                    {"text": "line 1\nline 2\nline 3"},
                    {"text": "line 4\nline 5\nline 6"},
                ],
            },
        ],
        "generationConfig": {'temperature': 0.0},
    }
    #
    result = tested.to_dict()
    assert result == expected
    # for log
    result = tested.to_dict(True)
    assert result == expected


@patch("commander.protocols.llms.llm_google.requests_post")
@patch.object(log, "info")
@patch.object(LlmGoogle, "to_dict")
def test_chat(to_dict, info, requests_post):
    def reset_mocks():
        to_dict.reset_mock()
        info.reset_mock()
        requests_post.reset_mock()

    tested = LlmGoogle("apiKey", "theModel")

    # error
    to_dict.side_effect = [{"key": "value"}]
    requests_post.return_value.status_code = 202
    requests_post.return_value.text = "theResponse"

    result = tested.chat()
    expected = JsonExtract("the reported error is: 202", True, [])
    assert result == expected

    calls = [call()]
    assert to_dict.mock_calls == calls
    calls = [
        call("***********"),
        call(202),
        call("theResponse"),
        call("***********"),
    ]
    assert info.mock_calls == calls
    calls = [call(
        "https://generativelanguage.googleapis.com/v1beta/theModel:generateContent?key=apiKey",
        headers={"Content-Type": "application/json"},
        params={},
        data='{"key": "value"}',
        verify=True,
        timeout=None,
    )]
    assert requests_post.mock_calls == calls
    reset_mocks()

    # no error
    # -- with log
    to_dict.side_effect = [{"key": "value"}]
    requests_post.return_value.status_code = 200
    requests_post.return_value.text = json.dumps({
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "\n".join([
                            '```json',
                            '["line 1","line 2","line 3"]',
                            '```',
                            '',
                        ])},
                    ],
                },
            },
        ],
    })

    result = tested.chat(True)
    expected = JsonExtract("", False, ["line 1", "line 2", "line 3"])
    assert result == expected

    calls = [call()]
    assert to_dict.mock_calls == calls
    calls = [
        call("***** CHAT STARTS ******"),
        call('```json\n["line 1","line 2","line 3"]\n```\n'),
        call("****** CHAT ENDS *******"),
    ]
    assert info.mock_calls == calls
    calls = [call(
        "https://generativelanguage.googleapis.com/v1beta/theModel:generateContent?key=apiKey",
        headers={"Content-Type": "application/json"},
        params={},
        data='{"key": "value"}',
        verify=True,
        timeout=None,
    )]
    assert requests_post.mock_calls == calls
    reset_mocks()
    # -- without log
    to_dict.side_effect = [{"key": "value"}]
    requests_post.return_value.status_code = 200
    requests_post.return_value.text = json.dumps({
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "\n".join([
                            '```json',
                            '["line 1","line 2","line 3"]',
                            '```',
                            '',
                        ])},
                    ],
                },
            },
        ],
    })

    result = tested.chat()
    expected = JsonExtract("", False, ["line 1", "line 2", "line 3"])
    assert result == expected

    calls = [call()]
    assert to_dict.mock_calls == calls
    assert info.mock_calls == []
    calls = [call(
        "https://generativelanguage.googleapis.com/v1beta/theModel:generateContent?key=apiKey",
        headers={"Content-Type": "application/json"},
        params={},
        data='{"key": "value"}',
        verify=True,
        timeout=None,
    )]
    assert requests_post.mock_calls == calls
    reset_mocks()
