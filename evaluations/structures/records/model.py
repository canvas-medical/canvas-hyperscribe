from typing import NamedTuple


class Model(NamedTuple):
    vendor: str = ""
    api_key: str = ""
    model: str = ""
    id: int = 0
