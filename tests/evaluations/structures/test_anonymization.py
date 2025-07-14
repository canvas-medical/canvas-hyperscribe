from evaluations.structures.anonymization import Anonymization
from evaluations.structures.anonymization_substitution import AnonymizationSubstitution
from evaluations.structures.case_exchange import CaseExchange
from tests.helper import is_namedtuple


def test_class():
    tested = Anonymization
    fields = {
        "source": list[CaseExchange],
        "result": list[CaseExchange],
        "substitutions": list[AnonymizationSubstitution],
    }
    assert is_namedtuple(tested, fields)
