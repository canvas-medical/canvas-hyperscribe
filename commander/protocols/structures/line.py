from typing import NamedTuple


class Line(NamedTuple):
    speaker: str
    text: str

    @classmethod
    def load_from_json(cls, json_list: list) -> list["Line"]:
        return [
            Line(
                speaker=json_object.get("speaker", ""),
                text=json_object.get("text", ""),
            )
            for json_object in json_list
        ]

    def to_json(self) -> dict:
        return {
            "speaker": self.speaker,
            "text": self.text,
        }
