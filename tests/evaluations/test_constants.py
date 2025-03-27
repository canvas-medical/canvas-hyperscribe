from evaluations.constants import Constants
from tests.helper import is_constant


def test_constants():
    tested = Constants
    constants = {
        "GROUP_COMMON": "common",
        "TYPE_GENERAL": "general",
        "TYPE_SITUATIONAL": "situational",
        #
        "CANVAS_SDK_DB_HOST": "CANVAS_SDK_DB_HOST",
        #
        "EVALUATIONS_DB_NAME": "EVALUATIONS_DB_NAME",
        "EVALUATIONS_DB_USERNAME": "EVALUATIONS_DB_USERNAME",
        "EVALUATIONS_DB_PASSWORD": "EVALUATIONS_DB_PASSWORD",
        "EVALUATIONS_DB_HOST": "EVALUATIONS_DB_HOST",
        "EVALUATIONS_DB_PORT": "EVALUATIONS_DB_PORT",
    }
    assert is_constant(tested, constants)
