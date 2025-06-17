from typing import NamedTuple

from evaluations.constants import Constants


class EvaluationCase(NamedTuple):
    environment: str = ""
    patient_uuid: str = ""
    limited_cache: dict = {}
    case_type: str = Constants.TYPE_GENERAL
    case_group: str = Constants.GROUP_COMMON
    case_name: str = ""
    cycles: int = 0
    description: str = ""
