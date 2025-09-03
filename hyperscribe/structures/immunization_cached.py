from __future__ import annotations

from datetime import date
from typing import NamedTuple


class ImmunizationCached(NamedTuple):
    uuid: str
    label: str
    code_cpt: str
    code_cvx: str
    comments: str
    approximate_date: date

    def to_dict(self) -> dict:
        return {
            "uuid": self.uuid,
            "label": self.label,
            "codeCpt": self.code_cpt,
            "codeCvx": self.code_cvx,
            "comments": self.comments,
            "approximateDate": self.approximate_date.isoformat(),
        }

    @classmethod
    def load_from_json(cls, data: dict) -> ImmunizationCached:
        return cls(
            uuid=data["uuid"],
            label=data["label"],
            code_cpt=data["codeCpt"],
            code_cvx=data["codeCvx"],
            comments=data["comments"],
            approximate_date=date.fromisoformat(data["approximateDate"]),
        )

    @classmethod
    def load_from_json_list(cls, data: list[dict]) -> list[ImmunizationCached]:
        return [cls.load_from_json(item) for item in data]
