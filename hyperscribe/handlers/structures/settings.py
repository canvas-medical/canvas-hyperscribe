from __future__ import annotations

from typing import NamedTuple

from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.structures.vendor_key import VendorKey


class Settings(NamedTuple):
    llm_text: VendorKey
    llm_audio: VendorKey
    science_host: str
    ontologies_host: str
    pre_shared_key: str
    structured_rfv: bool

    @classmethod
    def from_dictionary(cls, dictionary: dict) -> Settings:
        structured_rfv = dictionary.get(Constants.SECRET_STRUCTURED_RFV)
        return Settings(
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
            structured_rfv=bool(isinstance(structured_rfv, str) and structured_rfv.lower() in ["yes", "y", "1"]),
        )
