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
        "IGNORED_KEY_VALUE": ">?<",
        "CASE_CYCLE_SUFFIX": "cycle",
        #
        "OPTION_DIFFERENCE_LEVELS": "--evaluation-difference-levels",
        "OPTION_PATIENT_UUID": "--patient-uuid",
        "OPTION_PRINT_LOGS": "--print-logs",
        "OPTION_STORE_LOGS": "--store-logs",
        "OPTION_END2END": "--end2end",
        #
        "EVALUATIONS_DB_NAME": "EVALUATIONS_DB_NAME",
        "EVALUATIONS_DB_USERNAME": "EVALUATIONS_DB_USERNAME",
        "EVALUATIONS_DB_PASSWORD": "EVALUATIONS_DB_PASSWORD",
        "EVALUATIONS_DB_HOST": "EVALUATIONS_DB_HOST",
        "EVALUATIONS_DB_PORT": "EVALUATIONS_DB_PORT",
        #
        "AUDIO2TRANSCRIPT": "audio2transcript",
        "INSTRUCTION2PARAMETERS": "instruction2parameters",
        "PARAMETERS2COMMAND": "parameters2command",
        "STAGED_QUESTIONNAIRES": "staged_questionnaires",
        "TRANSCRIPT2INSTRUCTIONS": "transcript2instructions",
        "POSITIVE_VALUE": "positive",
        "NEGATIVE_VALUE": "negative", 
        "TURN_BUCKETS": {
            "short": (2, 4),
            "medium": (6, 8),
            "long": (10, 14),
            },
        "MOOD_POOL": [
        "patient is frustrated", "patient is tearful", "patient is embarrassed",
        "patient is defensive", "clinician is concerned", "clinician is rushed",
        "clinician is warm", "clinician is brief"
        ],
        "PRESSURE_POOL": [
            "time pressure on the visit", "insurance denied prior authorization",
            "formulary change", "refill limit reached", "patient traveling soon",
            "side‑effect report just came in"
        ],
        "CLINICIAN_PERSONAS": [
        "warm and chatty", "brief and efficient", "cautious and inquisitive",
        "over‑explainer"
        ],

        "PATIENT_PERSONAS": [
            "anxious and talkative", "confused and forgetful",
            "assertive and informed", "agreeable but vague"
        ]
    }
    assert is_constant(tested, constants)
