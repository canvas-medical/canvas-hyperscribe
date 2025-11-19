import re

from hyperscribe.libraries.helper_csv import HelperCsv
from tests.helper import is_constant


def test_constants():
    tested = HelperCsv
    constants = {
        # vvv not ideal but at least prevent any unwanted changed
        "PATTERN_VALUE": re.compile(r'(?:^|,)(?:"((?:[^"]|"")*)"|([^",]*))'),
    }
    assert is_constant(tested, constants)


def test_escape():
    tested = HelperCsv
    tests = [
        ("", ""),
        ("", ""),  # noqa
        ("some text", "some text"),
        ('some "text"', '"some ""text"""'),
        ("some, text", '"some, text"'),
    ]
    for string, expected in tests:
        result = tested.escape(string)
        assert result == expected, f"---> {string}"


def test_parse_line():
    tested = HelperCsv
    tests = [
        ("", [""]),
        ("abc", ["abc"]),
        ("abc,def", ["abc", "def"]),
        ('abc,"some ""text""",def', ["abc", 'some "text"', "def"]),
    ]
    for line, expected in tests:
        result = tested.parse_line(line)
        assert result == expected, f"---> {line}"


def test_int_value():
    tested = HelperCsv
    tests = [
        ("", 0),
        ("abc", 0),
        ("123xyz", 0),
        ("123", 123),
        ("1", 1),
        ("3258963", 3258963),
    ]
    for value, expected in tests:
        result = tested.int_value(value)
        assert result == expected, f"---> {value}"


def test_float_value():
    tested = HelperCsv
    tests = [
        ("", 0.0),
        ("abc", 0.0),
        ("123xyz", 0.0),
        ("123", 123.0),
        ("1", 1.0),
        ("1.8", 1.8),
        ("325.8963", 325.8963),
    ]
    for value, expected in tests:
        result = tested.float_value(value)
        assert result == expected, f"---> {value}"


def test_bool_value():
    tested = HelperCsv
    tests = [
        ("true", True),
        ("false", False),
        ("1", True),
        ("0", False),
        ("yes", True),
        ("y", True),
        ("no", False),
        ("2", False),
    ]
    for value, expected in tests:
        result = tested.bool_value(value)
        assert result is expected, f"---> {value}"
