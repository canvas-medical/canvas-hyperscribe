from evaluations.constants import Constants
from tests.helper import is_constant


def test_constants():
    tested = Constants
    constants = {
        "GROUP_COMMON": "common",
        "TYPE_GENERAL": "general",
        "TYPE_SITUATIONAL": "situational",
        #
        "DIFFERENCE_LEVEL_MINOR": "minor",
        "DIFFERENCE_LEVEL_MODERATE": "moderate",
        "DIFFERENCE_LEVEL_CRITICAL": "critical",
        "DIFFERENCE_LEVEL_SEVERE": "severe",
        "DIFFERENCE_LEVELS": [
            "minor",
            "moderate",
            "severe",
            "critical",
        ],
        #
        "OPTION_DIFFERENCE_LEVELS": "--evaluation-difference-levels",
        "OPTION_PATIENT_UUID": "--patient-uuid",
        "OPTION_PRINT_LOGS": "--print-logs",
        "OPTION_STORE_LOGS": "--store-logs",
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
