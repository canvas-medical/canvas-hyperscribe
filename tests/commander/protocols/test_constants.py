from commander.protocols.constants import Constants
from tests.helper import is_constant


def test_constants():
    tested = Constants
    constants = {
        "GOOGLE_CHAT_ALL": "models/gemini-1.5-flash",
        "MAX_ATTEMPTS_LLM_HTTP": 3,
        "MAX_ATTEMPTS_LLM_JSON": 3,
        "MAX_WORKERS": 10,
        "OPENAI_CHAT_AUDIO": "gpt-4o-audio-preview",
        "OPENAI_CHAT_TEXT": "gpt-4o",
        "VENDOR_GOOGLE": "Google",
        "VENDOR_OPENAI": "OpenAI",
        "SCHEMA_KEY_ALLERGY": "allergy",
        "SCHEMA_KEY_ASSESS": "assess",
        "SCHEMA_KEY_CLOSE_GOAL": "closeGoal",
        "SCHEMA_KEY_DIAGNOSE": "diagnose",
        "SCHEMA_KEY_FAMILY_HISTORY": "familyHistory",
        "SCHEMA_KEY_FOLLOW_UP": "followUp",
        "SCHEMA_KEY_GOAL": "goal",
        "SCHEMA_KEY_HISTORY_OF_PRESENT_ILLNESS": "hpi",
        "SCHEMA_KEY_IMAGING_ORDER": "imagingOrder",
        "SCHEMA_KEY_IMMUNIZE": "immunize",
        "SCHEMA_KEY_INSTRUCT": "instruct",
        "SCHEMA_KEY_LAB_ORDER": "labOrder",
        "SCHEMA_KEY_MEDICAL_HISTORY": "medicalHistory",
        "SCHEMA_KEY_MEDICATION": "medicationStatement",
        "SCHEMA_KEY_PHYSICAL_EXAM": "exam",
        "SCHEMA_KEY_PLAN": "plan",
        "SCHEMA_KEY_PRESCRIPTION": "prescribe",
        "SCHEMA_KEY_QUESTIONNAIRE": "questionnaire",
        "SCHEMA_KEY_REASON_FOR_VISIT": "reasonForVisit",
        "SCHEMA_KEY_REFILL": "refill",
        "SCHEMA_KEY_REMOVE_ALLERGY": "removeAllergy",
        "SCHEMA_KEY_STOP_MEDICATION": "stopMedication",
        "SCHEMA_KEY_SURGERY_HISTORY": "surgicalHistory",
        "SCHEMA_KEY_TASK": "task",
        "SCHEMA_KEY_UPDATE_DIAGNOSE": "updateDiagnosis",
        "SCHEMA_KEY_UPDATE_GOAL": "updateGoal",
        "SCHEMA_KEY_VITALS": "vitals",
    }
    assert is_constant(tested, constants)
