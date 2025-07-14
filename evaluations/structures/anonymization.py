from typing import NamedTuple

from evaluations.structures.anonymization_substitution import AnonymizationSubstitution
from evaluations.structures.case_exchange import CaseExchange


class Anonymization(NamedTuple):
    source: list[CaseExchange]
    result: list[CaseExchange]
    substitutions: list[AnonymizationSubstitution]
