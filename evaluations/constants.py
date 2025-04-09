class Constants:
    # case meta information
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
    #
    OPTION_DIFFERENCE_LEVELS = "--evaluation-difference-levels"
    OPTION_PATIENT_UUID = "--patient-uuid"
    OPTION_PRINT_LOGS = "--print-logs"
    OPTION_STORE_LOGS = "--store-logs"
    # environment variables
    # -- used to identify the running CANVAS instance
    CUSTOMER_IDENTIFIER = "CUSTOMER_IDENTIFIER"
    # -- credentials to access the PostGreSQL database storing the evaluation test results
    EVALUATIONS_DB_NAME = "EVALUATIONS_DB_NAME"
    EVALUATIONS_DB_USERNAME = "EVALUATIONS_DB_USERNAME"
    EVALUATIONS_DB_PASSWORD = "EVALUATIONS_DB_PASSWORD"
    EVALUATIONS_DB_HOST = "EVALUATIONS_DB_HOST"
    EVALUATIONS_DB_PORT = "EVALUATIONS_DB_PORT"
