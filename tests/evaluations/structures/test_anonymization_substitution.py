from evaluations.structures.anonymization_substitution import AnonymizationSubstitution
from tests.helper import is_namedtuple


def test_class():
    tested = AnonymizationSubstitution
    fields = {
        "original_entity": str,
        "anonymized_with": str,
    }
    assert is_namedtuple(tested, fields)


def test_load_from_json():
    tested = AnonymizationSubstitution
    result = tested.load_from_json([
        {"originalEntity": "theOriginalEntity1", "anonymizedWith": "theAnonymizedWith1"},
        {"originalEntity": "theOriginalEntity2", "anonymizedWith": "theAnonymizedWith2"},
        {"originalEntity": "theOriginalEntity3", "anonymizedWith": "theAnonymizedWith3"},
    ])
    expected = [
        AnonymizationSubstitution(original_entity="theOriginalEntity1", anonymized_with="theAnonymizedWith1"),
        AnonymizationSubstitution(original_entity="theOriginalEntity2", anonymized_with="theAnonymizedWith2"),
        AnonymizationSubstitution(original_entity="theOriginalEntity3", anonymized_with="theAnonymizedWith3"),
    ]
    assert result == expected


def test_to_json():
    tested = AnonymizationSubstitution(original_entity="theOriginalEntity", anonymized_with="theAnonymizedWith")
    result = tested.to_json()
    expected = {
        "originalEntity": "theOriginalEntity",
        "anonymizedWith": "theAnonymizedWith",
    }
    assert result == expected
