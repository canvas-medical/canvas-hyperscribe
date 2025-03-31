from typing import NamedTuple


class JsonExtract(NamedTuple):
    error: str
    has_error: bool
    content: list
