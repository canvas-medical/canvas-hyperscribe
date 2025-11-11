from __future__ import annotations


class TokenCounts:
    def __init__(self, prompt: int, generated: int):
        self.prompt = prompt
        self.generated = generated

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
