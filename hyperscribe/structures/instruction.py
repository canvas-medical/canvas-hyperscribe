from __future__ import annotations


class Instruction:
    def __init__(self, uuid: str, index: int, instruction: str, information: str, is_new: bool, is_updated: bool):
        self.uuid: str = uuid
        self.index: int = index
        self.instruction: str = instruction
        self.information: str = information
        self.previous_information: str = ""
        self.is_new: bool = is_new
        self.is_updated: bool = is_updated

    def set_previous_information(self, previous_information: str) -> Instruction:
        # using typing.Self would simplify the code of the subclasses
        self.previous_information = previous_information
        return self

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

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, Instruction)
        return (
            self.uuid == other.uuid
            and self.instruction == other.instruction
            and self.information == other.information
            and self.previous_information == other.previous_information
            and self.is_new == other.is_new
            and self.is_updated == other.is_updated
        )
