from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.review_of_system import ReviewOfSystem


def test_class():
    tested = ReviewOfSystem
    assert issubclass(tested, Base)


def test_schema_key():
    tested = ReviewOfSystem
    result = tested.schema_key()
    expected = "ros"
    assert result == expected


def test_staged_command_extract():
    tested = ReviewOfSystem
    tests = [
        ({}, None),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
