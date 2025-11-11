from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TokenCounts:
    prompt: int
    generated: int

    def add(self, counts: TokenCounts) -> None:
        self.prompt = self.prompt + counts.prompt
        self.generated = self.generated + counts.generated

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, TokenCounts)
        return self.prompt == other.prompt and self.generated == other.generated

    def to_dict(self) -> dict:
        return {
            "prompt": self.prompt,
            "generated": self.generated,
        }
