from __future__ import annotations

from typing import NamedTuple


class CustomPrompt(NamedTuple):
    command: str
    prompt: str

    @classmethod
    def load_from_json_list(cls, data: list[dict]) -> list[CustomPrompt]:
        return [
            CustomPrompt(
                command=item["command"],
                prompt=item["prompt"],
            )
            for item in data
        ]
