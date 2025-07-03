from typing import NamedTuple, Optional


class VendorKey(NamedTuple):
    vendor: str
    api_key: str
    model: Optional[str] = None
    temperature: Optional[float] = None
