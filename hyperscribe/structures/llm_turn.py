from __future__ import annotations

from typing import NamedTuple


class LlmTurn(NamedTuple):
    role: str
    text: list[str]

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "text": self.text,
        }

    @classmethod
    def load_from_json(cls, json_list: list) -> list[LlmTurn]:
        return [
            LlmTurn(
                role=json_object.get("role", ""),
                text=json_object.get("text", ""),
            )
            for json_object in json_list
        ]
