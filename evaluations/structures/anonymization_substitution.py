from __future__ import annotations

from typing import NamedTuple


class AnonymizationSubstitution(NamedTuple):
    original_entity: str
    anonymized_with: str

    @classmethod
    def load_from_json(cls, json_list: list) -> list[AnonymizationSubstitution]:
        return [
            cls(
                original_entity=json_object["originalEntity"],
                anonymized_with=json_object["anonymizedWith"],
            )
            for json_object in json_list
        ]

    def to_json(self) -> dict:
        return {
            "originalEntity": self.original_entity,
            "anonymizedWith": self.anonymized_with,
        }
