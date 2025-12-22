from datetime import datetime, date
from enum import Enum
from re import match
from typing import Type, Any

from canvas_sdk.clients.llms import LlmSettings
from canvas_sdk.clients.llms.structures.settings import (
    LlmSettingsAnthropic,
    LlmSettingsGemini,
    LlmSettingsGpt4,
    LlmSettingsGpt5,
)
from canvas_sdk.utils.db import thread_cleanup
from canvas_sdk.v1.data.note import NoteStateChangeEvent, NoteStates

from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.llms.llm_anthropic import LlmAnthropic
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.llms.llm_eleven_labs import LlmElevenLabs
from hyperscribe.llms.llm_google import LlmGoogle
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.model_spec import ModelSpec
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
    def chatter(cls, settings: Settings, memory_log: MemoryLog, model_spec: ModelSpec) -> LlmBase:
        api_key = settings.llm_text.api_key
        model = settings.llm_text_model(model_spec)
        if settings.llm_text.vendor.upper() == Constants.VENDOR_GOOGLE.upper():
            return LlmGoogle(
                LlmSettingsGemini(api_key=api_key, model=model, temperature=0.0),
                memory_log,
                settings.audit_llm,
            )
        elif settings.llm_text.vendor.upper() == Constants.VENDOR_ANTHROPIC.upper():
            llm_settings = LlmSettingsAnthropic(
                api_key=api_key,
                model=model,
                temperature=0.0,
                max_tokens=64000,
            )
            return LlmAnthropic(llm_settings, memory_log, settings.audit_llm)
        else:
            llm_settings = LlmSettingsGpt4(api_key=api_key, model=model, temperature=0.0)
            if model.lower().startswith("gpt-5.1") or model.lower().startswith("o"):
                effort = "none"
                verbosity = "medium"
                if settings.reasoning_llm:
                    effort = "high"
                    verbosity = "high"

                llm_settings = LlmSettingsGpt5(
                    api_key=api_key,
                    model=model,
                    reasoning_effort=effort,
                    text_verbosity=verbosity,
                )
            return LlmOpenai(llm_settings, memory_log, settings.audit_llm)

    @classmethod
    def audio2texter(cls, settings: Settings, memory_log: MemoryLog) -> LlmBase:
        llm_settings = LlmSettings(
            api_key=settings.llm_audio.api_key,
            model=settings.llm_audio_model(),
        )
        return LlmElevenLabs(llm_settings, memory_log, settings.audit_llm)

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

    @classmethod
    def editable_note(cls, note_id: int) -> bool:
        current_note_state = NoteStateChangeEvent.objects.filter(note_id=note_id).order_by("created").last()
        return bool(
            current_note_state
            and current_note_state.state
            in [
                NoteStates.NEW,
                NoteStates.PUSHED,
                NoteStates.UNLOCKED,
                NoteStates.RESTORED,
                NoteStates.UNDELETED,
                NoteStates.CONVERTED,
            ]
        )
