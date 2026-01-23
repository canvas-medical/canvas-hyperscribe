from __future__ import annotations


class Instruction:
    def __init__(
        self,
        uuid: str,
        index: int,
        instruction: str,
        information: str,
        is_new: bool,
        is_updated: bool,
        previous_information: str,
        prefilled_template: str = "",
    ):
        self.uuid = uuid
        self.index = index
        self.instruction = instruction
        self.information = information
        self.is_new = is_new
        self.is_updated = is_updated
        self.previous_information = previous_information
        self.prefilled_template = prefilled_template

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
                prefilled_template=json_object.get("prefilledTemplate", ""),
            )
            for json_object in json_list
        ]

    def to_json(self, reset_flags: bool) -> dict:
        result = {
            "uuid": self.uuid,
            "index": self.index,
            "instruction": self.instruction,
            "information": self.information,
            "isNew": False if reset_flags else self.is_new,
            "isUpdated": False if reset_flags else self.is_updated,
        }
        if self.prefilled_template:
            result["prefilledTemplate"] = self.prefilled_template
        return result

    def limited_str(self) -> str:
        return (
            f"{self.instruction} #{self.index:02d} "
            f"({self.uuid}, new/updated: {self.is_new}/{self.is_updated}): {self.information}"
        )

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, Instruction)
        return (
            self.uuid == other.uuid
            and self.index == other.index
            and self.instruction == other.instruction
            and self.information == other.information
            and self.previous_information == other.previous_information
            and self.prefilled_template == other.prefilled_template
            and self.is_new == other.is_new
            and self.is_updated == other.is_updated
        )
