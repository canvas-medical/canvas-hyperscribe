from typing import NamedTuple


class Instruction(NamedTuple):
    uuid: str
    instruction: str
    information: str

    @classmethod
    def load_from_json(cls, json_list: list) -> list["Instruction"]:
        return [
            Instruction(
                uuid=json_object.get("uuid", ""),
                instruction=json_object.get("instruction", ""),
                information=json_object.get("information", ""),
            )
            for json_object in json_list
        ]

    def to_json(self) -> dict:
        return {
            "uuid": self.uuid,
            "instruction": self.instruction,
            "information": self.information,
        }
