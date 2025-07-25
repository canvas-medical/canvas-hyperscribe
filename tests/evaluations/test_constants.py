from evaluations.constants import Constants
from tests.helper import is_constant
from evaluations.structures.enums.synthetic_case_turn_buckets import SyntheticCaseTurnBuckets


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
        "DIFFERENCE_LEVELS": ["minor", "moderate", "severe", "critical"],
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
        "TURN_TOTAL": "turn_total",
        "SPEAKER_SEQUENCE": "speaker_sequence",
        "TARGET_C_TO_P_WORD_RATIO": "target_C_to_P_word_ratio",
        "RATIO": "ratio",
        "MOOD_KEY": "mood",
        "PRESSURE_KEY": "pressure",
        "CLINICIAN_STYLE_KEY": "clinician_style",
        "PATIENT_STYLE_KEY": "patient_style",
        "BUCKET": "bucket",
        "TURN_BUCKETS": {
            SyntheticCaseTurnBuckets.SHORT: (2, 4),
            SyntheticCaseTurnBuckets.MEDIUM: (6, 8),
            SyntheticCaseTurnBuckets.LONG: (10, 14),
        },
        "EXAMPLE_CHART_DESCRIPTIONS": {
            "demographicStr": "string describing patient demographics",
            "conditionHistory": "patient history of conditions",
            "currentAllergies": "current allergies for the patient",
            "currentConditions": "current patient conditions and diagnoses",
            "currentMedications": "current patient medications being taken",
            "currentGoals": "current treatment goals for the patient",
            "familyHistory": "any history of family care or illness",
            "surgeryHistory": "any history of surgical care or operations",
        },
    }
    assert is_constant(tested, constants)
