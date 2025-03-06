from datetime import datetime, date
from enum import Enum
from re import match
from typing import Type

from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.llms.llm_anthropic import LlmAnthropic
from hyperscribe.handlers.llms.llm_base import LlmBase
from hyperscribe.handlers.llms.llm_google import LlmGoogle
from hyperscribe.handlers.llms.llm_openai import LlmOpenai
from hyperscribe.handlers.memory_log import MemoryLog
from hyperscribe.handlers.structures.settings import Settings


class Helper:

    @classmethod
    def str2datetime(cls, string: str | None) -> datetime | None:
        try:
            return datetime.strptime(string, "%Y-%m-%d")
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
            return LlmGoogle(memory_log, settings.llm_text.api_key, Constants.GOOGLE_CHAT_ALL)
        if settings.llm_text.vendor.upper() == Constants.VENDOR_ANTHROPIC.upper():
            return LlmAnthropic(memory_log, settings.llm_text.api_key, Constants.ANTHROPIC_CHAT_TEXT)
        # if settings.llm_text.upper() == Constants.VENDOR_OPENAI.upper():
        return LlmOpenai(memory_log, settings.llm_text.api_key, Constants.OPENAI_CHAT_TEXT)

    @classmethod
    def audio2texter(cls, settings: Settings, memory_log: MemoryLog) -> LlmBase:
        if settings.llm_audio.vendor.upper() == Constants.VENDOR_GOOGLE.upper():
            return LlmGoogle(memory_log, settings.llm_audio.api_key, Constants.GOOGLE_CHAT_ALL)
        # if settings.llm_text.upper() == Constants.VENDOR_OPENAI.upper():
        return LlmOpenai(memory_log, settings.llm_audio.api_key, Constants.OPENAI_CHAT_AUDIO)
