from __future__ import annotations
from typing import NamedTuple


class ChartItem(NamedTuple):
    code: str
    label: str
    uuid: str

    def to_json(self) -> dict:
        return {
            "code": self.code,
            "label": self.label,
            "uuid": self.uuid,
        }

    @classmethod
    def load_from_json(cls, data: dict) -> ChartItem:
        return cls(
            code=data["code"],
            label=data["label"],
            uuid=data["uuid"],
        )
