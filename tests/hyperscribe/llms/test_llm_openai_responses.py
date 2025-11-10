import json
from unittest.mock import patch, call, MagicMock

from hyperscribe.llms.llm_openai_responses import LlmOpenaiResponses
from hyperscribe.structures.http_response import HttpResponse
from hyperscribe.structures.token_counts import TokenCounts


def test_support_speaker_identification():
    memory_log = MagicMock()
    tested = LlmOpenaiResponses(memory_log, "openaiKey", "theModel", False)
    result = tested.support_speaker_identification()
    assert result is False


def test_to_dict():
    memory_log = MagicMock()
    #
    tested = LlmOpenaiResponses(memory_log, "openaiKey", "theModel", False)
    tested.set_system_prompt(["line 1", "line 2", "line 3"])
    tested.set_user_prompt(["line 4", "line 5", "line 6"])
    result = tested.to_dict()
    expected = {
        "input": [
            {
                "content": [
                    {
                        "text": "line 4\nline 5\nline 6",
                        "type": "input_text",
                    },
                ],
                "role": "user",
            },
        ],
        "instructions": "line 1\nline 2\nline 3",
        "modalities": ["text"],
        "model": "theModel",
        "temperature": 0.0,
    }

    assert result == expected
    assert memory_log.mock_calls == []

    # with a model starting with gpt-5
    tested = LlmOpenaiResponses(memory_log, "openaiKey", "gpt-5-model", False)
    tested.set_system_prompt(["line 1", "line 2", "line 3"])
    tested.set_user_prompt(["line 4", "line 5", "line 6"])
    result = tested.to_dict()
    expected = {
        "input": [
            {
                "content": [
                    {
                        "text": "line 4\nline 5\nline 6",
                        "type": "input_text",
                    },
                ],
                "role": "user",
            },
        ],
        "instructions": "line 1\nline 2\nline 3",
        "model": "gpt-5-model",
    }

    assert result == expected
    assert memory_log.mock_calls == []

    # with an exchange with the model
    tested = LlmOpenaiResponses(memory_log, "openaiKey", "theModel", False)
    tested.set_system_prompt(["line 1", "line 2", "line 3"])
    tested.set_user_prompt(["line 4", "line 5", "line 6"])
    tested.set_model_prompt(["line 7", "line 8"])
    tested.set_user_prompt(["line 9", "line 10"])
    result = tested.to_dict()
    expected = {
        "input": [
            {
                "content": [
                    {
                        "text": "line 4\nline 5\nline 6",
                        "type": "input_text",
                    },
                ],
                "role": "user",
            },
            {
                "content": [
                    {
                        "text": "line 7\nline 8",
                        "type": "output_text",
                    },
                ],
                "role": "assistant",
            },
            {
                "content": [
                    {
                        "text": "line 9\nline 10",
                        "type": "input_text",
                    },
                ],
                "role": "user",
            },
        ],
        "instructions": "line 1\nline 2\nline 3",
        "modalities": ["text"],
        "model": "theModel",
        "temperature": 0.0,
    }

    assert result == expected
    assert memory_log.mock_calls == []


@patch("hyperscribe.llms.llm_openai_responses.requests_post")
def test_request(requests_post):
    memory_log = MagicMock()

    def reset_mocks():
        requests_post.reset_mock()
        memory_log.reset_mock()

    response = type(
        "Response",
        (),
        {
            "status_code": 202,
            "text": json.dumps(
                {
                    "output": [
                        {
                            "type": "other",
                        },
                        {
                            "type": "message",
                            "content": [
                                {
                                    "text": "\n".join(
                                        [
                                            "response:",
                                            "```json",
                                            json.dumps(["item1", "item2"]),
                                            "```",
                                            "",
                                            "```json",
                                            json.dumps(["item3"]),
                                            "```",
                                            "",
                                            "end.",
                                        ],
                                    ),
                                }
                            ],
                        },
                    ],
                    "usage": {
                        "input_tokens": 178,
                        "output_tokens": 93,
                    },
                },
            ),
        },
    )()
    tested = LlmOpenaiResponses(memory_log, "openaiKey", "theModel", False)
    # all good
    response.status_code = 200
    expected = HttpResponse(
        code=200,
        response='response:\n```json\n["item1", "item2"]\n```\n\n```json\n["item3"]\n```\n\nend.',
        tokens=TokenCounts(prompt=178, generated=93),
    )
    calls_request_post = [
        call(
            "https://us.api.openai.com/v1/responses",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer openaiKey",
            },
            params={},
            data=json.dumps(
                {
                    "model": "theModel",
                    "instructions": "",
                    "input": [],
                    "modalities": ["text"],
                    "temperature": 0.0,
                }
            ),
            verify=True,
            timeout=None,
        ),
    ]
    requests_post.side_effect = [response]
    result = tested.request()

    assert result == expected
    assert requests_post.mock_calls == calls_request_post
    calls = [
        call.log("--- request begins:"),
        call.log(
            "{"
            '\n  "model": "theModel",'
            '\n  "instructions": "",'
            '\n  "input": [],'
            '\n  "modalities": ['
            '\n    "text"'
            "\n  ],"
            '\n  "temperature": 0.0'
            "\n}"
        ),
        call.log("status code: 200"),
        call.log(
            '{"output": [{"type": "other"}, {'
            '"type": "message", '
            '"content": [{"text": "response:\\n'
            "```json\\n"
            '[\\"item1\\", \\"item2\\"]\\n```\\n\\n```json\\n[\\"item3\\"]\\n'
            "```\\n\\n"
            'end."}]}], '
            '"usage": {"input_tokens": 178, "output_tokens": 93}}'
        ),
        call.log("--- request ends ---"),
    ]
    assert memory_log.mock_calls == calls
    reset_mocks()

    # error
    response.status_code = 500
    requests_post.side_effect = [response]
    result = tested.request()
    exp_with_error = HttpResponse(
        code=500,
        response='{"output": [{"type": "other"}, {"type": "message", "content": [{"text": '
        '"response:\\n'
        "```json\\n"
        '[\\"item1\\", \\"item2\\"]\\n'
        "```\\n\\n"
        "```json\\n"
        '[\\"item3\\"]\\n'
        "```\\n\\n"
        'end."}]}], '
        '"usage": {"input_tokens": 178, "output_tokens": 93}}',
        tokens=TokenCounts(prompt=0, generated=0),
    )
    assert result == exp_with_error
    assert requests_post.mock_calls == calls_request_post
    calls = [
        call.log("--- request begins:"),
        call.log(
            "{"
            '\n  "model": "theModel",'
            '\n  "instructions": "",'
            '\n  "input": [],'
            '\n  "modalities": [\n    "text"\n  ],'
            '\n  "temperature": 0.0\n}'
        ),
        call.log("status code: 500"),
        call.log(
            '{"output": [{"type": "other"}, {"type": "message", "content": [{"text": '
            '"response:\\n'
            "```json\\n"
            '[\\"item1\\", \\"item2\\"]\\n'
            "```\\n\\n"
            "```json\\n"
            '[\\"item3\\"]\\n'
            "```\\n\\n"
            'end."}]}], '
            '"usage": {"input_tokens": 178, "output_tokens": 93}}'
        ),
        call.log("--- request ends ---"),
    ]
    assert memory_log.mock_calls == calls
    reset_mocks()
