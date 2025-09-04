from pathlib import Path

from evaluations.structures.anonymization_result import AnonymizationResult
from evaluations.structures.anonymization_substitution import AnonymizationSubstitution
from tests.helper import is_namedtuple


def test_class():
    tested = AnonymizationResult
    fields = {
        "files": list[Path],
        "substitutions": list[AnonymizationSubstitution],
    }
    assert is_namedtuple(tested, fields)
