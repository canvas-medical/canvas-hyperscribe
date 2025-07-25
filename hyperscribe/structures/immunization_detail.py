from typing import NamedTuple


class ImmunizationDetail(NamedTuple):
    label: str
    code_cpt: str
    code_cvx: str
    cvx_description: str
