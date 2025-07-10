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
