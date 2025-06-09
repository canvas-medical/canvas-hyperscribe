from __future__ import annotations

from typing import NamedTuple


class ChargeDescription(NamedTuple):
    full_name: str
    short_name: str
    cpt_code: str

    @classmethod
    def load_from_json(cls, data: dict) -> ChargeDescription:
        return cls(
            full_name=data["fullName"],
            short_name=data["shortName"],
            cpt_code=data["cptCode"],
        )
