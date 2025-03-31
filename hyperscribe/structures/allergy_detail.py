from typing import NamedTuple


class AllergyDetail(NamedTuple):
    concept_id_value: int
    concept_id_description: str
    concept_type: str
    concept_id_type: int
