from __future__ import annotations

from datetime import date
from typing import NamedTuple


class ImmunizationCached(NamedTuple):
    uuid: str
    label: str
    code_cpt: str
    code_cvx: str
    comments: str
    approximate_date: date | None

    def to_dict(self) -> dict:
        return {
            "uuid": self.uuid,
            "label": self.label,
            "codeCpt": self.code_cpt,
            "codeCvx": self.code_cvx,
            "comments": self.comments,
            "approximateDate": self.approximate_date.isoformat() if self.approximate_date else None,
        }

    def approximate_date_str(self) -> str:
        return self.approximate_date.isoformat() if self.approximate_date else ""

    @classmethod
    def load_from_json(cls, data: dict) -> ImmunizationCached:
        approximate_date: date | None = None
        if data["approximateDate"]:
            approximate_date = date.fromisoformat(data["approximateDate"])
        return cls(
            uuid=data["uuid"],
            label=data["label"],
            code_cpt=data["codeCpt"],
            code_cvx=data["codeCvx"],
            comments=data["comments"],
            approximate_date=approximate_date,
        )

    @classmethod
    def load_from_json_list(cls, data: list[dict]) -> list[ImmunizationCached]:
        return [cls.load_from_json(item) for item in data]
