from __future__ import annotations
from typing import NamedTuple


class PatientProfile(NamedTuple):
    name: str
    profile: str

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "profile": self.profile,
        }

    @classmethod
    def load_from_json(cls, data: dict) -> PatientProfile:
        return cls(
            name=data["name"],
            profile=data["profile"],
        )
