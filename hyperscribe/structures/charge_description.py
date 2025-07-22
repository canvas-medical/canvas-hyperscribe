from __future__ import annotations

from typing import NamedTuple


class ChargeDescription(NamedTuple):
    full_name: str
    short_name: str
    cpt_code: str

    def to_dict(self) -> dict:
        return {"fullName": self.full_name, "shortName": self.short_name, "cptCode": self.cpt_code}

    @classmethod
    def load_from_json(cls, data: dict) -> ChargeDescription:
        return cls(
            full_name=data.get("fullName") or data.get("full_name") or "",
            short_name=data.get("shortName") or data.get("short_name") or "",
            cpt_code=data.get("cptCode") or data.get("cpt_code") or "",
        )
