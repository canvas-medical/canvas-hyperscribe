from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instruction:
    uuid: str
    instruction: str
    information: str
    is_new: bool
    is_updated: bool
    audits: list[str]  # is not affected by the frozen when using append

    @classmethod
    def load_from_json(cls, json_list: list) -> list[Instruction]:
        return [
            Instruction(
                uuid=json_object.get("uuid", ""),
                instruction=json_object.get("instruction", ""),
                information=json_object.get("information", ""),
                is_new=json_object.get("isNew", True),
                is_updated=json_object.get("isUpdated", False),
                audits=json_object.get("audits", []),
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

    def limited_str(self) -> str:
        return f"{self.instruction} ({self.uuid}, new/updated: {self.is_new}/{self.is_updated}): {self.information}"
