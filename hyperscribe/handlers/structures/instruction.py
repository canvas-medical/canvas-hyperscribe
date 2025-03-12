from __future__ import annotations

from typing import NamedTuple


class Instruction(NamedTuple):
    uuid: str
    instruction: str
    information: str
    is_new: bool
    is_updated: bool

    @classmethod
    def load_from_json(cls, json_list: list) -> list[Instruction]:
        return [
            Instruction(
                uuid=json_object.get("uuid", ""),
                instruction=json_object.get("instruction", ""),
                information=json_object.get("information", ""),
                is_new=json_object.get("isNew", True),
                is_updated=json_object.get("isUpdated", False),
            )
            for json_object in json_list
        ]

    def to_json(self) -> dict:
        return {
            "uuid": self.uuid,
            "instruction": self.instruction,
            "information": self.information,
            "isNew": False,
            "isUpdated": False,
        }
