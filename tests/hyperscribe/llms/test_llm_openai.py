from http import HTTPStatus
from unittest.mock import patch, call, MagicMock

from canvas_sdk.clients.llms import LlmOpenai as LlmOpenaiBase, LlmTokens, LlmResponse
from canvas_sdk.clients.llms import LlmSettings

from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.llms.llm_openai import LlmOpenai


def test_class():
    assert issubclass(LlmOpenai, LlmOpenaiBase)
    assert issubclass(LlmOpenai, LlmBase)


def test_support_speaker_identification():
    llm_settings = LlmSettings(api_key="theKey", model="theModel")
    memory_log = MagicMock()
    tested = LlmOpenai(llm_settings, memory_log, False)
    result = tested.support_speaker_identification()
    assert result is True


@patch("hyperscribe.llms.llm_openai.requests_post")
def test_audio_to_text(requests_post):
    memory_log = MagicMock()

    def reset_mocks():
        requests_post.reset_mock()
        memory_log.reset_mock()

    requests_post.return_value.status_code = 202
    requests_post.return_value.text = "theResponse"

    llm_settings = LlmSettings(api_key="theKey", model="theModel")
    tested = LlmOpenai(llm_settings, memory_log, False)
    result = tested.audio_to_text(b"abc")
    expected = LlmResponse(code=HTTPStatus(202), response="theResponse", tokens=LlmTokens(prompt=0, generated=0))
    assert result == expected
    calls = [
        call(
            "https://us.api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": "Bearer theKey"},
            params={},
            data={
                "model": "whisper-1",
                "language": "en",
                "prompt": "The conversation is in the medical context.",
                "response_format": "text",
            },
            files={"file": ("audio.mp3", b"abc", "application/octet-stream")},
            verify=True,
        ),
    ]
    assert requests_post.mock_calls == calls
    assert memory_log.mock_calls == []
    reset_mocks()
