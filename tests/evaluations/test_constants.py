from evaluations.constants import Constants
from tests.helper import is_constant


def test_constants():
    tested = Constants
    constants = {
        "CANVAS_SDK_DB_HOST": "CANVAS_SDK_DB_HOST",
        "TYPE_SITUATIONAL": "situational",
        "TYPE_GENERAL": "general",
        "GROUP_COMMON": "common",
    }
    assert is_constant(tested, constants)
