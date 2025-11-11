from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Instruction:
    uuid: str
    index: int
    instruction: str
    information: str
    is_new: bool
    is_updated: bool
    previous_information: str

    @classmethod
    def load_from_json(cls, json_list: list) -> list[Instruction]:
        return [
            Instruction(
                uuid=json_object.get("uuid", ""),
                index=json_object.get("index", 0),
                instruction=json_object.get("instruction", ""),
                information=json_object.get("information", ""),
                is_new=json_object.get("isNew", True),
                is_updated=json_object.get("isUpdated", False),
                previous_information="",
            )
            for json_object in json_list
        ]

    def to_json(self, reset_flags: bool) -> dict:
        return {
            "uuid": self.uuid,
            "index": self.index,
            "instruction": self.instruction,
            "information": self.information,
            "isNew": False if reset_flags else self.is_new,
            "isUpdated": False if reset_flags else self.is_updated,
        }

    def limited_str(self) -> str:
        return (
            f"{self.instruction} #{self.index:02d} "
            f"({self.uuid}, new/updated: {self.is_new}/{self.is_updated}): {self.information}"
        )
