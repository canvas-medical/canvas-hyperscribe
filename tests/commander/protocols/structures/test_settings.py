from commander.protocols.structures.settings import Settings
from tests.helper import is_namedtuple


def test_class():
    tested = Settings
    fields = {
        "openai_key": str,
        "science_host": str,
        "ontologies_host": str,
        "pre_shared_key": str,
        "allow_update": bool,
    }
    assert is_namedtuple(tested, fields)
