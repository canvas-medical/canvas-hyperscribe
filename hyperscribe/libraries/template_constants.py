"""Constants for note_templates plugin integration."""

# Cache key prefix (must match note_templates/utils/constants.py)
COMMAND_PERMISSIONS_KEY_PREFIX = "note_template_cmd_perms_"

# Exceptions where Hyperscribe class name != simple f"{name}Command" pattern.
# All other commands follow the default: ClassName -> ClassNameCommand.
_COMMAND_TYPE_OVERRIDES: dict[str, str] = {
    "Medication": "MedicationStatementCommand",
    "Prescription": "PrescribeCommand",
    "ReviewOfSystem": "ReviewOfSystemsCommand",
    "SurgeryHistory": "PastSurgicalHistoryCommand",
    "UpdateDiagnose": "UpdateDiagnosisCommand",
}


def get_command_type(hyperscribe_class_name: str) -> str:
    """Convert a Hyperscribe class name to its Canvas SDK command type name."""
    return _COMMAND_TYPE_OVERRIDES.get(
        hyperscribe_class_name,
        f"{hyperscribe_class_name}Command",
    )


# Mapping from Hyperscribe class names to Canvas SDK schema_keys (for querying commands).
# Only includes commands with free-text fields (narrative, comment, background, etc.)
# where template framework detection via note content is relevant. Structured-data
# commands (prescriptions, vitals, questionnaires, etc.) are intentionally omitted.
HYPERSCRIBE_TO_SCHEMA_KEY: dict[str, str] = {
    "Allergy": "allergy",
    "Assess": "assess",
    "CloseGoal": "closeGoal",
    "Diagnose": "diagnose",
    "FamilyHistory": "familyHistory",
    "FollowUp": "followUp",
    "Goal": "goal",
    "HistoryOfPresentIllness": "hpi",
    "Instruct": "instruct",
    "LabOrder": "labOrder",
    "MedicalHistory": "medicalHistory",
    "Perform": "perform",
    "Plan": "plan",
    "ReasonForVisit": "reasonForVisit",
    "Refer": "refer",
    "Task": "task",
    "UpdateDiagnose": "updateDiagnosis",
    "UpdateGoal": "updateGoal",
}


def get_schema_key(hyperscribe_class_name: str) -> str | None:
    """Convert a Hyperscribe class name to its Canvas SDK schema_key, or None if not mapped."""
    return HYPERSCRIBE_TO_SCHEMA_KEY.get(hyperscribe_class_name)
