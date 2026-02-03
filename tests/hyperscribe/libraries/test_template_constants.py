"""Tests for template_constants module."""

from hyperscribe.libraries.template_constants import (
    COMMAND_PERMISSIONS_KEY_PREFIX,
    ADD_CONTENT_KEY_PREFIX,
    FREE_TEXT_FIELDS,
    HYPERSCRIBE_TO_COMMAND_TYPE,
    get_command_type,
    get_free_text_fields,
)


class TestConstants:
    """Tests for constant values."""

    def test_command_permissions_key_prefix(self):
        """Test COMMAND_PERMISSIONS_KEY_PREFIX matches note_templates plugin."""
        assert COMMAND_PERMISSIONS_KEY_PREFIX == "note_template_cmd_perms_"

    def test_add_content_key_prefix(self):
        """Test ADD_CONTENT_KEY_PREFIX matches note_templates plugin."""
        assert ADD_CONTENT_KEY_PREFIX == "note_template_add_content_"

    def test_free_text_fields_has_expected_commands(self):
        """Test FREE_TEXT_FIELDS contains expected command types."""
        expected_commands = [
            "HistoryOfPresentIllnessCommand",
            "AssessCommand",
            "PlanCommand",
            "DiagnoseCommand",
            "AllergyCommand",
            "PrescribeCommand",
            "LabOrderCommand",
            "TaskCommand",
        ]
        for cmd in expected_commands:
            assert cmd in FREE_TEXT_FIELDS, f"{cmd} should be in FREE_TEXT_FIELDS"

    def test_free_text_fields_hpi_has_narrative(self):
        """Test HistoryOfPresentIllnessCommand has narrative field."""
        assert "narrative" in FREE_TEXT_FIELDS["HistoryOfPresentIllnessCommand"]

    def test_free_text_fields_assess_has_both_fields(self):
        """Test AssessCommand has background and narrative fields."""
        assert "background" in FREE_TEXT_FIELDS["AssessCommand"]
        assert "narrative" in FREE_TEXT_FIELDS["AssessCommand"]

    def test_free_text_fields_diagnose_has_expected_fields(self):
        """Test DiagnoseCommand has expected fields."""
        assert "background" in FREE_TEXT_FIELDS["DiagnoseCommand"]
        assert "today_assessment" in FREE_TEXT_FIELDS["DiagnoseCommand"]

    def test_free_text_fields_questionnaire_is_empty(self):
        """Test QuestionnaireCommand has empty list (handled dynamically)."""
        assert FREE_TEXT_FIELDS["QuestionnaireCommand"] == []


class TestHyperscribeToCommandType:
    """Tests for HYPERSCRIBE_TO_COMMAND_TYPE mapping."""

    def test_history_of_present_illness_mapping(self):
        """Test HistoryOfPresentIllness maps correctly."""
        assert HYPERSCRIBE_TO_COMMAND_TYPE["HistoryOfPresentIllness"] == "HistoryOfPresentIllnessCommand"

    def test_assess_mapping(self):
        """Test Assess maps correctly."""
        assert HYPERSCRIBE_TO_COMMAND_TYPE["Assess"] == "AssessCommand"

    def test_diagnose_mapping(self):
        """Test Diagnose maps correctly."""
        assert HYPERSCRIBE_TO_COMMAND_TYPE["Diagnose"] == "DiagnoseCommand"

    def test_plan_mapping(self):
        """Test Plan maps correctly."""
        assert HYPERSCRIBE_TO_COMMAND_TYPE["Plan"] == "PlanCommand"

    def test_medication_maps_to_medication_statement(self):
        """Test Medication maps to MedicationStatementCommand."""
        assert HYPERSCRIBE_TO_COMMAND_TYPE["Medication"] == "MedicationStatementCommand"

    def test_prescription_maps_to_prescribe(self):
        """Test Prescription maps to PrescribeCommand."""
        assert HYPERSCRIBE_TO_COMMAND_TYPE["Prescription"] == "PrescribeCommand"

    def test_surgery_history_maps_to_past_surgical_history(self):
        """Test SurgeryHistory maps to PastSurgicalHistoryCommand."""
        assert HYPERSCRIBE_TO_COMMAND_TYPE["SurgeryHistory"] == "PastSurgicalHistoryCommand"

    def test_update_diagnose_maps_correctly(self):
        """Test UpdateDiagnose maps to UpdateDiagnosisCommand."""
        assert HYPERSCRIBE_TO_COMMAND_TYPE["UpdateDiagnose"] == "UpdateDiagnosisCommand"

    def test_review_of_system_maps_correctly(self):
        """Test ReviewOfSystem maps to ReviewOfSystemsCommand (plural)."""
        assert HYPERSCRIBE_TO_COMMAND_TYPE["ReviewOfSystem"] == "ReviewOfSystemsCommand"


class TestGetCommandType:
    """Tests for get_command_type function."""

    def test_known_class_name(self):
        """Test get_command_type with a known class name."""
        result = get_command_type("HistoryOfPresentIllness")
        assert result == "HistoryOfPresentIllnessCommand"

    def test_unknown_class_name_appends_command(self):
        """Test get_command_type with unknown class name appends Command."""
        result = get_command_type("UnknownClass")
        assert result == "UnknownClassCommand"

    def test_all_mapped_classes(self):
        """Test all classes in mapping return correct command type."""
        for class_name, expected_type in HYPERSCRIBE_TO_COMMAND_TYPE.items():
            result = get_command_type(class_name)
            assert result == expected_type, f"Failed for {class_name}"


class TestGetFreeTextFields:
    """Tests for get_free_text_fields function."""

    def test_known_command_type(self):
        """Test get_free_text_fields with known command type."""
        result = get_free_text_fields("HistoryOfPresentIllnessCommand")
        assert result == ["narrative"]

    def test_assess_command(self):
        """Test get_free_text_fields for AssessCommand."""
        result = get_free_text_fields("AssessCommand")
        assert "background" in result
        assert "narrative" in result

    def test_unknown_command_type_returns_empty(self):
        """Test get_free_text_fields with unknown command type."""
        result = get_free_text_fields("UnknownCommand")
        assert result == []

    def test_questionnaire_command_returns_empty(self):
        """Test get_free_text_fields for QuestionnaireCommand."""
        result = get_free_text_fields("QuestionnaireCommand")
        assert result == []

    def test_prescribe_command_has_sig_and_note(self):
        """Test PrescribeCommand has sig and note_to_pharmacist fields."""
        result = get_free_text_fields("PrescribeCommand")
        assert "sig" in result
        assert "note_to_pharmacist" in result
