from __future__ import annotations

from typing import NamedTuple


class MedicationCached(NamedTuple):
    uuid: str
    label: str
    code_rx_norm: str
    code_fdb: str
    national_drug_code: str
    potency_unit_code: str

    def to_dict(self) -> dict:
        return {
            "uuid": self.uuid,
            "label": self.label,
            "codeRxNorm": self.code_rx_norm,
            "codeFdb": self.code_fdb,
            "nationalDrugCode": self.national_drug_code,
            "potencyUnitCode": self.potency_unit_code,
        }

    @classmethod
    def load_from_json(cls, data: dict) -> MedicationCached:
        if "code" in data:
            # previous encoding
            return cls(
                uuid=data["uuid"],
                label=data["label"],
                code_rx_norm=data["code"],
                code_fdb="",
                national_drug_code="",
                potency_unit_code="",
            )
        return cls(
            uuid=data["uuid"],
            label=data["label"],
            code_rx_norm=data["codeRxNorm"],
            code_fdb=data["codeFdb"],
            national_drug_code=data["nationalDrugCode"],
            potency_unit_code=data["potencyUnitCode"],
        )

    @classmethod
    def load_from_json_list(cls, data: list[dict]) -> list[MedicationCached]:
        return [cls.load_from_json(item) for item in data]
