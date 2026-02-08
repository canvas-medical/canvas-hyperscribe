"""Tests for template_constants module."""

from hyperscribe.libraries.template_constants import (
    COMMAND_PERMISSIONS_KEY_PREFIX,
    _COMMAND_TYPE_OVERRIDES,
    get_command_type,
    get_schema_key,
)


class TestConstants:
    def test_command_permissions_key_prefix(self):
        assert COMMAND_PERMISSIONS_KEY_PREFIX == "note_template_cmd_perms_"


class TestCommandTypeOverrides:
    """Only non-obvious mappings are in the override dict."""

    def test_medication_maps_to_medication_statement(self):
        assert _COMMAND_TYPE_OVERRIDES["Medication"] == "MedicationStatementCommand"

    def test_prescription_maps_to_prescribe(self):
        assert _COMMAND_TYPE_OVERRIDES["Prescription"] == "PrescribeCommand"

    def test_surgery_history_maps_to_past_surgical_history(self):
        assert _COMMAND_TYPE_OVERRIDES["SurgeryHistory"] == "PastSurgicalHistoryCommand"

    def test_update_diagnose_maps_correctly(self):
        assert _COMMAND_TYPE_OVERRIDES["UpdateDiagnose"] == "UpdateDiagnosisCommand"

    def test_review_of_system_maps_correctly(self):
        assert _COMMAND_TYPE_OVERRIDES["ReviewOfSystem"] == "ReviewOfSystemsCommand"

    def test_only_five_overrides(self):
        assert len(_COMMAND_TYPE_OVERRIDES) == 5


class TestGetCommandType:
    def test_default_pattern(self):
        assert get_command_type("HistoryOfPresentIllness") == "HistoryOfPresentIllnessCommand"

    def test_override_applied(self):
        assert get_command_type("Medication") == "MedicationStatementCommand"

    def test_unknown_class_name_appends_command(self):
        assert get_command_type("UnknownClass") == "UnknownClassCommand"

    def test_all_overrides_returned(self):
        for class_name, expected_type in _COMMAND_TYPE_OVERRIDES.items():
            assert get_command_type(class_name) == expected_type, f"Failed for {class_name}"


class TestGetSchemaKey:
    def test_history_of_present_illness_returns_hpi(self):
        assert get_schema_key("HistoryOfPresentIllness") == "hpi"

    def test_plan_returns_plan(self):
        assert get_schema_key("Plan") == "plan"

    def test_assess_returns_assess(self):
        assert get_schema_key("Assess") == "assess"

    def test_unknown_class_returns_none(self):
        assert get_schema_key("UnknownClass") is None

    def test_reason_for_visit_returns_reasonforvisit(self):
        assert get_schema_key("ReasonForVisit") == "reasonForVisit"
