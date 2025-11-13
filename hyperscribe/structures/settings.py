from __future__ import annotations

import json
import re
from typing import NamedTuple

from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.custom_prompt import CustomPrompt
from hyperscribe.structures.model_spec import ModelSpec
from hyperscribe.structures.vendor_key import VendorKey


class Settings(NamedTuple):
    api_signing_key: str
    llm_text: VendorKey
    llm_audio: VendorKey
    structured_rfv: bool
    audit_llm: bool
    reasoning_llm: bool
    is_tuning: bool
    max_workers: int
    hierarchical_detection_threshold: int
    send_progress: bool
    commands_policy: AccessPolicy
    staffers_policy: AccessPolicy
    trial_staffers_policy: AccessPolicy
    cycle_transcript_overlap: int
    custom_prompts: list[CustomPrompt]

    @classmethod
    def from_dictionary(cls, dictionary: dict) -> Settings:
        return cls._from_dict_base(dictionary, False)

    @classmethod
    def from_dict_with_reasoning(cls, dictionary: dict) -> Settings:
        return cls._from_dict_base(
            dictionary,
            bool(dictionary.get(Constants.TEXT_MODEL_TYPE) == Constants.TEXT_MODEL_REASONING),
        )

    @classmethod
    def _from_dict_base(cls, dictionary: dict, reasoning_llm: bool) -> Settings:
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
            structured_rfv=cls.is_true(dictionary.get(Constants.SECRET_STRUCTURED_RFV)),
            audit_llm=cls.is_true(dictionary.get(Constants.SECRET_AUDIT_LLM)),
            reasoning_llm=reasoning_llm,
            is_tuning=cls.is_true(dictionary.get(Constants.SECRET_IS_TUNING)),
            max_workers=cls.clamp_int(
                dictionary.get(Constants.SECRET_MAX_WORKERS),
                Constants.MAX_WORKERS_MIN,
                Constants.MAX_WORKERS_MAX,
                Constants.MAX_WORKERS_DEFAULT,
            ),
            hierarchical_detection_threshold=cls.clamp_int(
                dictionary.get(Constants.SECRET_HIERARCHICAL_DETECTION_THRESHOLD),
                Constants.HIERARCHICAL_DETECTION_THRESHOLD_MIN,
                Constants.HIERARCHICAL_DETECTION_THRESHOLD_MAX,
                Constants.HIERARCHICAL_DETECTION_THRESHOLD_DEFAULT,
            ),
            send_progress=dictionary.get(Constants.PROGRESS_SETTING_KEY, False),
            commands_policy=AccessPolicy(
                policy=cls.is_true(dictionary.get(Constants.SECRET_COMMANDS_POLICY)),
                items=cls.list_from(dictionary.get(Constants.SECRET_COMMANDS_LIST)),
            ),
            staffers_policy=AccessPolicy(
                policy=cls.is_true(dictionary.get(Constants.SECRET_STAFFERS_POLICY)),
                items=cls.list_from(dictionary.get(Constants.SECRET_STAFFERS_LIST)),
            ),
            trial_staffers_policy=AccessPolicy(
                policy=True,
                items=cls.list_from(dictionary.get(Constants.SECRET_TRIAL_STAFFERS_LIST)),
            ),
            cycle_transcript_overlap=cls.clamp_int(
                dictionary.get(Constants.SECRET_CYCLE_TRANSCRIPT_OVERLAP),
                Constants.CYCLE_TRANSCRIPT_OVERLAP_MIN,
                Constants.CYCLE_TRANSCRIPT_OVERLAP_MAX,
                Constants.CYCLE_TRANSCRIPT_OVERLAP_DEFAULT,
            ),
            custom_prompts=CustomPrompt.load_from_json_list(
                json.loads(dictionary.get(Constants.SECRET_CUSTOM_PROMPTS) or "[]") or []
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
        if self.llm_audio.vendor.upper() == Constants.VENDOR_ELEVEN_LABS.upper():
            result = Constants.ELEVEN_LABS_AUDIO
        return result

    def llm_text_model(self, model_spec: ModelSpec) -> str:
        if self.reasoning_llm:
            result = Constants.OPENAI_REASONING_TEXT
            if self.llm_text.vendor.upper() == Constants.VENDOR_GOOGLE.upper():
                result = Constants.GOOGLE_REASONING_TEXT
            elif self.llm_text.vendor.upper() == Constants.VENDOR_ANTHROPIC.upper():
                result = Constants.ANTHROPIC_REASONING_TEXT
            return result

        result = Constants.OPENAI_CHAT_TEXT
        if self.llm_text.vendor.upper() == Constants.VENDOR_GOOGLE.upper():
            result = Constants.GOOGLE_CHAT_ALL
        elif self.llm_text.vendor.upper() == Constants.VENDOR_ANTHROPIC.upper():
            result = Constants.ANTHROPIC_CHAT_TEXT

        if model_spec.value == ModelSpec.SIMPLER.value:
            return result.split()[-1]
        elif model_spec.value == ModelSpec.COMPLEX.value:
            return result.split()[0]
        return result  # <--- not used with the APIs - just for logging

    def llm_text_temperature(self) -> float:
        result = 0.0
        if self.llm_text_model(ModelSpec.SIMPLER) == Constants.OPENAI_CHAT_TEXT_O3:
            result = Constants.O3_TEMPERATURE
        return result
