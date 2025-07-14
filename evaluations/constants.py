from evaluations.structures.enums.synthetic_case_mood import SyntheticCaseMood
from evaluations.structures.enums.synthetic_case_pressure import SyntheticCasePressure
from evaluations.structures.enums.synthetic_case_clinician_style import SyntheticCaseClinicianStyle
from evaluations.structures.enums.synthetic_case_patient_style import SyntheticCasePatientStyle
from evaluations.structures.enums.synthetic_case_turn_buckets import SyntheticCaseTurnBuckets

class Constants:
    # case meta-information
    GROUP_COMMON = "common"
    TYPE_GENERAL = "general"
    TYPE_SITUATIONAL = "situational"
    #
    DIFFERENCE_LEVEL_MINOR = "minor"
    DIFFERENCE_LEVEL_MODERATE = "moderate"
    DIFFERENCE_LEVEL_CRITICAL = "critical"
    DIFFERENCE_LEVEL_SEVERE = "severe"
    DIFFERENCE_LEVELS = [
        DIFFERENCE_LEVEL_MINOR,
        DIFFERENCE_LEVEL_MODERATE,
        DIFFERENCE_LEVEL_SEVERE,
        DIFFERENCE_LEVEL_CRITICAL,
    ]
    IGNORED_KEY_VALUE = ">?<"
    CASE_CYCLE_SUFFIX = "cycle"
    #
    OPTION_DIFFERENCE_LEVELS = "--evaluation-difference-levels"
    OPTION_PATIENT_UUID = "--patient-uuid"
    OPTION_PRINT_LOGS = "--print-logs"
    OPTION_STORE_LOGS = "--store-logs"
    OPTION_END2END = "--end2end"
    # environment variables
    # -- credentials to access the PostGreSQL database storing the evaluation test results
    EVALUATIONS_DB_NAME = "EVALUATIONS_DB_NAME"
    EVALUATIONS_DB_USERNAME = "EVALUATIONS_DB_USERNAME"
    EVALUATIONS_DB_PASSWORD = "EVALUATIONS_DB_PASSWORD"
    EVALUATIONS_DB_HOST = "EVALUATIONS_DB_HOST"
    EVALUATIONS_DB_PORT = "EVALUATIONS_DB_PORT"
    #
    AUDIO2TRANSCRIPT = "audio2transcript"
    INSTRUCTION2PARAMETERS = "instruction2parameters"
    PARAMETERS2COMMAND = "parameters2command"
    STAGED_QUESTIONNAIRES = "staged_questionnaires"
    TRANSCRIPT2INSTRUCTIONS = "transcript2instructions"
    POSITIVE_VALUE = "positive"
    RAW_TEXT_CUTOFF = 5000
    TURN_BUCKETS = {
        "short": (2, 4),
        "medium": (6, 8),
        "long": (10, 14),
    }

    MOOD_POOL = [
        "patient is frustrated", "patient is tearful", "patient is embarrassed",
        "patient is defensive", "clinician is concerned", "clinician is rushed",
        "clinician is warm", "clinician is brief"
    ]

    PRESSURE_POOL = [
        "time pressure on the visit", "insurance denied prior authorization",
        "formulary change", "refill limit reached", "patient traveling soon",
        "side effect report just came in"
    ]

    CLINICIAN_PERSONAS = [
        "warm and chatty", "brief and efficient", "cautious and inquisitive",
        "over explainer"
    ]

    PATIENT_PERSONAS = [
        "anxious and talkative", "confused and forgetful",
        "assertive and informed", "agreeable but vague"
    ]

    MOOD_MAP = {
    "patient is frustrated": SyntheticCaseMood.PATIENT_FRUSTRATED,
    "patient is tearful": SyntheticCaseMood.PATIENT_TEARFUL,
    "patient is embarrassed": SyntheticCaseMood.PATIENT_EMBARRASSED,
    "patient is defensive": SyntheticCaseMood.PATIENT_DEFENSIVE,
    "clinician is concerned": SyntheticCaseMood.CLINICIAN_CONCERNED,
    "clinician is rushed": SyntheticCaseMood.CLINICIAN_RUSHED,
    "clinician is warm": SyntheticCaseMood.CLINICIAN_WARM,
    "clinician is brief": SyntheticCaseMood.CLINICIAN_BRIEF,
    }

    PRESSURE_MAP = {
        "time pressure on the visit": SyntheticCasePressure.TIME_PRESSURE,
        "insurance denied prior authorization": SyntheticCasePressure.DENIED_AUTH,
        "formulary change": SyntheticCasePressure.FORMULARY,
        "refill limit reached": SyntheticCasePressure.REFILL_LIMIT,
        "patient traveling soon": SyntheticCasePressure.TRAVELING,
        "side effect report just came in": SyntheticCasePressure.SIDE_EFFECT,
    }

    CLINICIAN_STYLE_MAP = {
        "warm and chatty": SyntheticCaseClinicianStyle.WARM_CHATTY,
        "brief and efficient": SyntheticCaseClinicianStyle.BRIEF_EFFICIENT,
        "cautious and inquisitive": SyntheticCaseClinicianStyle.CAUTIOUS_INQUISITIVE,
        "over explainer": SyntheticCaseClinicianStyle.OVER_EXPLAIN,
    }

    PATIENT_STYLE_MAP = {
        "anxious and talkative": SyntheticCasePatientStyle.ANXIOUS_TALKATIVE,
        "confused and forgetful": SyntheticCasePatientStyle.CONFUSED_FORGETFUL,
        "assertive and informed": SyntheticCasePatientStyle.ASSERTIVE_INFORMED,
        "agreeable but vague": SyntheticCasePatientStyle.AGREEABLE_VAGUE,
    }

    TURN_BUCKETS_MAP = {
        "short": SyntheticCaseTurnBuckets.SHORT,
        "medium": SyntheticCaseTurnBuckets.MEDIUM,
        "long": SyntheticCaseTurnBuckets.LONG,
    }
