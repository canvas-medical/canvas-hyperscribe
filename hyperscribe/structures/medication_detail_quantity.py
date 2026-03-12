from typing import NamedTuple


class MedicationDetailQuantity(NamedTuple):
    quantity: str
    representative_ndc: str
    clinical_quantity_description: str
    ncpdp_quantity_qualifier_code: str
    ncpdp_quantity_qualifier_description: str
