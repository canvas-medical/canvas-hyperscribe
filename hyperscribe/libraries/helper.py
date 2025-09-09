from datetime import datetime, date
from enum import Enum
from re import match
from typing import Type, Any

from canvas_sdk.utils.db import thread_cleanup
from evaluations.constants import Constants as EvaluationConstants
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.llms.llm_anthropic import LlmAnthropic
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.llms.llm_eleven_labs import LlmElevenLabs
from hyperscribe.llms.llm_google import LlmGoogle
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.llms.llm_openai_o3 import LlmOpenaiO3
from hyperscribe.structures.settings import Settings


class Helper:
    @classmethod
    def with_cleanup(cls, fn: Any) -> Any:  # fn should be Callable, but it is not allowed as import yet
        """
        Decorator that calls thread_cleanup() after the wrapped function.
        """

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            finally:
                thread_cleanup()

        return wrapper

    @classmethod
    def str2datetime(cls, string: str | None) -> datetime | None:
        try:
            return datetime.strptime(string or "", "%Y-%m-%d")
        except Exception:
            return None

    @classmethod
    def str2date(cls, string: str | None) -> date | None:
        if result := cls.str2datetime(string):
            return result.date()
        return None

    @classmethod
    def enum_or_none(cls, value: str, enum: Type[Enum]) -> Enum | None:
        if value in (item.value for item in enum):
            return enum(value)
        return None

    @classmethod
    def icd10_add_dot(cls, code: str) -> str:
        if result := match(r"([A-Za-z]+\d{2})(\d+)", code):
            return f"{result.group(1)}.{result.group(2)}"
        return code

    @classmethod
    def icd10_strip_dot(cls, code: str) -> str:
        return code.replace(".", "")

    @classmethod
    def chatter(cls, settings: Settings, memory_log: MemoryLog) -> LlmBase:
        if settings.llm_text.vendor.upper() == Constants.VENDOR_GOOGLE.upper():
            return LlmGoogle(memory_log, settings.llm_text.api_key, settings.llm_text_model(), settings.audit_llm)
        elif settings.llm_text.vendor.upper() == Constants.VENDOR_ANTHROPIC.upper():
            return LlmAnthropic(memory_log, settings.llm_text.api_key, settings.llm_text_model(), settings.audit_llm)
        else:
            model = settings.llm_text_model()
            if model == Constants.OPENAI_CHAT_TEXT_O3:
                return LlmOpenaiO3(
                    memory_log,
                    settings.llm_text.api_key,
                    with_audit=settings.audit_llm,
                    temperature=EvaluationConstants.O3_TEMPERATURE,
                )
            else:
                return LlmOpenai(memory_log, settings.llm_text.api_key, model, settings.audit_llm)

    @classmethod
    def audio2texter(cls, settings: Settings, memory_log: MemoryLog) -> LlmBase:
        result: Type[LlmBase] = LlmOpenai
        if settings.llm_audio.vendor.upper() == Constants.VENDOR_GOOGLE.upper():
            result = LlmGoogle
        elif settings.llm_audio.vendor.upper() == Constants.VENDOR_ELEVEN_LABS.upper():
            result = LlmElevenLabs
        return result(memory_log, settings.llm_audio.api_key, settings.llm_audio_model(), settings.audit_llm)

    @classmethod
    def canvas_host(cls, canvas_instance: str) -> str:
        result = f"https://{canvas_instance}.canvasmedical.com"
        if canvas_instance == "local":
            result = "http://localhost:8000"
        return result

    @classmethod
    def canvas_ws_host(cls, canvas_instance: str) -> str:
        result = f"wss://{canvas_instance}.canvasmedical.com"
        if canvas_instance == "local":
            result = "ws://localhost:8000"
        return result
