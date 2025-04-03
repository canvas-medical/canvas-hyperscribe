from typing import NamedTuple


class MedicationSearch(NamedTuple):
    comment: str
    keywords: list[str]
    brand_names: list[str]
    related_condition: str
