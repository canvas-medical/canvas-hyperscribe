import pytest

from hyperscribe_tuning.commands.base import Base


def test_class_name():
    tested = Base
    result = tested.class_name()
    expected = "Base"
    assert result == expected


def test_schema_key():
    tested = Base
    with pytest.raises(Exception) as e:
        _ = tested.schema_key()
    expected = "NotImplementedError"
    assert e.typename == expected


def test_staged_command_extract():
    tested = Base
    with pytest.raises(Exception) as e:
        _ = tested.staged_command_extract({})
    expected = "NotImplementedError"
    assert e.typename == expected
