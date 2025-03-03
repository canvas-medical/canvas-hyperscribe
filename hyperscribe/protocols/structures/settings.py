from typing import NamedTuple

from hyperscribe.protocols.structures.vendor_key import VendorKey


class Settings(NamedTuple):
    llm_text: VendorKey
    llm_audio: VendorKey
    science_host: str
    ontologies_host: str
    pre_shared_key: str
    structured_rfv: bool
