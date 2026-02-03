"""Constants for note_templates plugin integration.

This module defines shared constants used when integrating with the note_templates
plugin, including cache key prefixes and free text field mappings.
"""

# Cache key prefixes (must match note_templates/utils/constants.py)
COMMAND_PERMISSIONS_KEY_PREFIX = "note_template_cmd_perms_"
ADD_CONTENT_KEY_PREFIX = "note_template_add_content_"

# Free text fields by command type (matching note_templates/utils/constants.py)
# These are the fields that support {add:} instructions from templates
FREE_TEXT_FIELDS: dict[str, list[str]] = {
    "AdjustPrescriptionCommand": ["sig", "note_to_pharmacist"],
    "AllergyCommand": ["narrative"],
    "AssessCommand": ["background", "narrative"],
    "CloseGoalCommand": ["progress"],
    "DiagnoseCommand": ["background", "today_assessment"],
    "FamilyHistoryCommand": ["family_history", "relative", "note"],
    "FollowUpCommand": ["comment"],
    "GoalCommand": ["goal_statement", "progress"],
    "HistoryOfPresentIllnessCommand": ["narrative"],
    "ImagingOrderCommand": ["additional_details", "comment"],
    "ImagingReviewCommand": ["message_to_patient", "comment"],
    "InstructCommand": ["comment"],
    "LabOrderCommand": ["comment"],
    "LabReviewCommand": ["message_to_patient", "comment"],
    "MedicalHistoryCommand": ["past_medical_history", "comments"],
    "MedicationStatementCommand": ["sig"],
    "PastSurgicalHistoryCommand": ["past_surgical_history", "comment"],
    "PerformCommand": ["notes"],
    "PhysicalExamCommand": ["result"],
    "PlanCommand": ["narrative"],
    "PrescribeCommand": ["sig", "note_to_pharmacist"],
    "QuestionnaireCommand": [],  # TXT-type questions handled dynamically
    "ReasonForVisitCommand": ["comment"],
    "ReferCommand": ["notes_to_specialist", "comment"],
    "ReferralReviewCommand": ["message_to_patient", "comment"],
    "RefillCommand": ["sig", "note_to_pharmacist"],
    "RemoveAllergyCommand": ["narrative"],
    "ResolveConditionCommand": ["rationale"],
    "ReviewOfSystemsCommand": ["result"],
    "StopMedicationCommand": ["rationale"],
    "StructuredAssessmentCommand": ["result"],
    "TaskCommand": ["title", "comment"],
    "UncategorizedDocumentReviewCommand": ["message_to_patient", "comment"],
    "UpdateDiagnosisCommand": ["background", "narrative"],
    "UpdateGoalCommand": ["progress"],
    "VitalsCommand": ["note"],
}

# Mapping from Hyperscribe class names to Canvas SDK command type names
HYPERSCRIBE_TO_COMMAND_TYPE: dict[str, str] = {
    "AdjustPrescription": "AdjustPrescriptionCommand",
    "Allergy": "AllergyCommand",
    "Assess": "AssessCommand",
    "CloseGoal": "CloseGoalCommand",
    "Diagnose": "DiagnoseCommand",
    "FamilyHistory": "FamilyHistoryCommand",
    "FollowUp": "FollowUpCommand",
    "Goal": "GoalCommand",
    "HistoryOfPresentIllness": "HistoryOfPresentIllnessCommand",
    "ImagingOrder": "ImagingOrderCommand",
    "Immunize": "ImmunizeCommand",
    "ImmunizationStatement": "ImmunizationStatementCommand",
    "Instruct": "InstructCommand",
    "LabOrder": "LabOrderCommand",
    "MedicalHistory": "MedicalHistoryCommand",
    "Medication": "MedicationStatementCommand",
    "Perform": "PerformCommand",
    "PhysicalExam": "PhysicalExamCommand",
    "Plan": "PlanCommand",
    "Prescription": "PrescribeCommand",
    "Questionnaire": "QuestionnaireCommand",
    "ReasonForVisit": "ReasonForVisitCommand",
    "Refer": "ReferCommand",
    "Refill": "RefillCommand",
    "RemoveAllergy": "RemoveAllergyCommand",
    "ResolveCondition": "ResolveConditionCommand",
    "ReviewOfSystem": "ReviewOfSystemsCommand",
    "StopMedication": "StopMedicationCommand",
    "StructuredAssessment": "StructuredAssessmentCommand",
    "SurgeryHistory": "PastSurgicalHistoryCommand",
    "Task": "TaskCommand",
    "UpdateDiagnose": "UpdateDiagnosisCommand",
    "UpdateGoal": "UpdateGoalCommand",
    "Vitals": "VitalsCommand",
}


def get_command_type(hyperscribe_class_name: str) -> str:
    """Convert a Hyperscribe class name to its corresponding Canvas SDK command type.

    Args:
        hyperscribe_class_name: The Hyperscribe command class name (e.g., "HistoryOfPresentIllness")

    Returns:
        The corresponding Canvas SDK command type (e.g., "HistoryOfPresentIllnessCommand")
    """
    return HYPERSCRIBE_TO_COMMAND_TYPE.get(
        hyperscribe_class_name,
        f"{hyperscribe_class_name}Command",
    )


def get_free_text_fields(command_type: str) -> list[str]:
    """Get the free text fields for a given command type.

    Args:
        command_type: The Canvas SDK command type name

    Returns:
        List of field names that are free text fields, or empty list if none
    """
    return FREE_TEXT_FIELDS.get(command_type, [])
