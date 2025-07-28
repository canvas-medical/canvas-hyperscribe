from __future__ import annotations

from typing import NamedTuple


class CodedItem(NamedTuple):
    uuid: str
    label: str
    code: str

    def to_dict(self) -> dict:
        return {"uuid": self.uuid, "label": self.label, "code": self.code}

    @classmethod
    def load_from_json(cls, data: dict) -> CodedItem:
        return cls(uuid=data["uuid"], label=data["label"], code=data["code"])
