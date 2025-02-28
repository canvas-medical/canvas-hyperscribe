from typing import NamedTuple


class LlmTurn(NamedTuple):
    role: str
    text: list[str]
