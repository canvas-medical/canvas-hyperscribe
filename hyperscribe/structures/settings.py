from __future__ import annotations

import re
from typing import NamedTuple

from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.vendor_key import VendorKey


class Settings(NamedTuple):
    api_signing_key: str
    llm_text: VendorKey
    llm_audio: VendorKey
    science_host: str
    ontologies_host: str
    pre_shared_key: str
    structured_rfv: bool
    audit_llm: bool
    is_tuning: bool
    send_progress: bool
    commands_policy: AccessPolicy
    staffers_policy: AccessPolicy
    cycle_transcript_overlap: int

    @classmethod
    def from_dictionary(cls, dictionary: dict) -> Settings:
        return Settings(
            api_signing_key=dictionary[Constants.SECRET_API_SIGNING_KEY],
            llm_text=VendorKey(
                vendor=dictionary[Constants.SECRET_TEXT_LLM_VENDOR],
                api_key=dictionary[Constants.SECRET_TEXT_LLM_KEY],
            ),
            llm_audio=VendorKey(
                vendor=dictionary[Constants.SECRET_AUDIO_LLM_VENDOR],
                api_key=dictionary[Constants.SECRET_AUDIO_LLM_KEY],
            ),
            science_host=dictionary[Constants.SECRET_SCIENCE_HOST],
            ontologies_host=dictionary[Constants.SECRET_ONTOLOGIES_HOST],
            pre_shared_key=dictionary[Constants.SECRET_PRE_SHARED_KEY],
            structured_rfv=cls.is_true(dictionary.get(Constants.SECRET_STRUCTURED_RFV)),
            audit_llm=cls.is_true(dictionary.get(Constants.SECRET_AUDIT_LLM)),
            is_tuning=cls.is_true(dictionary.get(Constants.SECRET_IS_TUNING)),
            send_progress=dictionary.get(Constants.PROGRESS_SETTING_KEY, False),
            commands_policy=AccessPolicy(
                policy=cls.is_true(dictionary.get(Constants.SECRET_COMMANDS_POLICY)),
                items=cls.list_from(dictionary.get(Constants.SECRET_COMMANDS_LIST)),
            ),
            staffers_policy=AccessPolicy(
                policy=cls.is_true(dictionary.get(Constants.SECRET_STAFFERS_POLICY)),
                items=cls.list_from(dictionary.get(Constants.SECRET_STAFFERS_LIST)),
            ),
            cycle_transcript_overlap=cls.clamp_int(
                dictionary.get(Constants.SECRET_CYCLE_TRANSCRIPT_OVERLAP),
                Constants.CYCLE_TRANSCRIPT_OVERLAP_MIN,
                Constants.CYCLE_TRANSCRIPT_OVERLAP_MAX,
                Constants.CYCLE_TRANSCRIPT_OVERLAP_DEFAULT,
            ),
        )

    @classmethod
    def clamp_int(cls, value: int | str | None, low: int, high: int, default: int) -> int:
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        if isinstance(value, int):
            return min(max(value, low), high)
        return default

    @classmethod
    def is_true(cls, string: str | None) -> bool:
        return bool(isinstance(string, str) and string.lower() in ["yes", "y", "1"])

    @classmethod
    def list_from(cls, string: str | None) -> list:
        if isinstance(string, str):
            return sorted(re.findall(r"[a-zA-Z0-9]+", string))
        return []

    def llm_audio_model(self) -> str:
        result = Constants.OPENAI_CHAT_AUDIO
        if self.llm_audio.vendor.upper() == Constants.VENDOR_GOOGLE.upper():
            result = Constants.GOOGLE_CHAT_ALL
        return result

    def llm_text_model(self) -> str:
        result = Constants.OPENAI_CHAT_TEXT
        if self.llm_text.vendor.upper() == Constants.VENDOR_GOOGLE.upper():
            result = Constants.GOOGLE_CHAT_ALL
        elif self.llm_text.vendor.upper() == Constants.VENDOR_ANTHROPIC.upper():
            result = Constants.ANTHROPIC_CHAT_TEXT
        return result
