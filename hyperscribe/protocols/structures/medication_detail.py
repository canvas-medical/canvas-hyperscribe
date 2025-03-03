from typing import NamedTuple

from hyperscribe.protocols.structures.medication_detail_quantity import MedicationDetailQuantity


class MedicationDetail(NamedTuple):
    fdb_code: str
    description: str
    quantities: list[MedicationDetailQuantity]
