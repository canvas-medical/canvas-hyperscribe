from __future__ import annotations


class Instruction:
    def __init__(self, uuid: str, instruction: str, information: str, is_new: bool, is_updated: bool, audits: list[str]):
        self.uuid: str = uuid
        self.instruction: str = instruction
        self.information: str = information
        self.is_new: bool = is_new
        self.is_updated: bool = is_updated
        self.audits: list[str] = audits  # is not affected by the frozen when using append

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

    def __eq__(self, other: Instruction) -> bool:
        return (self.uuid == other.uuid and
                self.instruction == other.instruction and
                self.information == other.information and
                self.is_new == other.is_new and
                self.is_updated == other.is_updated)
