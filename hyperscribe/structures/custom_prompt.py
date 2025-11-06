from __future__ import annotations

from typing import NamedTuple


class CustomPrompt(NamedTuple):
    command: str
    prompt: str
    active: bool

    @classmethod
    def load_from_json_list(cls, data: list[dict]) -> list[CustomPrompt]:
        return [cls.load_from_json(item) for item in data]

    @classmethod
    def load_from_json(cls, data: dict) -> CustomPrompt:
        return CustomPrompt(
            command=data["command"],
            prompt=data["prompt"],
            active=data.get("active", True),
        )

    def to_json(self) -> dict:
        return {
            "command": self.command,
            "prompt": self.prompt,
            "active": self.active,
        }
