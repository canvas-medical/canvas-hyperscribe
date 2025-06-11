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
    send_progress: bool
    commands_policy: AccessPolicy
    staffers_policy: AccessPolicy

    @classmethod
    def from_dictionary(cls, dictionary: dict) -> Settings:
        return Settings(
            api_signing_key=dictionary[Constants.SECRET_API_SIGNING_KEY],
            llm_text=VendorKey(
                vendor=dictionary[Constants.SECRET_TEXT_VENDOR],
                api_key=dictionary[Constants.SECRET_TEXT_KEY],
            ),
            llm_audio=VendorKey(
                vendor=dictionary[Constants.SECRET_AUDIO_VENDOR],
                api_key=dictionary[Constants.SECRET_AUDIO_KEY],
            ),
            science_host=dictionary[Constants.SECRET_SCIENCE_HOST],
            ontologies_host=dictionary[Constants.SECRET_ONTOLOGIES_HOST],
            pre_shared_key=dictionary[Constants.SECRET_PRE_SHARED_KEY],
            structured_rfv=cls.is_true(dictionary.get(Constants.SECRET_STRUCTURED_RFV)),
            audit_llm=cls.is_true(dictionary.get(Constants.SECRET_AUDIT_LLM)),
            send_progress=dictionary.get(Constants.PROGRESS_SETTING_KEY, False),
            commands_policy=AccessPolicy(
                policy=cls.is_true(dictionary.get(Constants.SECRET_COMMANDS_POLICY)),
                items=cls.list_from(dictionary.get(Constants.SECRET_COMMANDS_LIST)),
            ),
            staffers_policy=AccessPolicy(
                policy=cls.is_true(dictionary.get(Constants.SECRET_STAFFERS_POLICY)),
                items=cls.list_from(dictionary.get(Constants.SECRET_STAFFERS_LIST)),
            )
        )

    @classmethod
    def is_true(cls, string: str | None) -> bool:
        return bool(isinstance(string, str) and string.lower() in ["yes", "y", "1"])

    @classmethod
    def list_from(cls, string: str | None) -> list:
        if isinstance(string, str):
            return sorted(re.findall(r'[a-zA-Z0-9]+', string))
        return []
