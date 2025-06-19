import sys
import os
import json
from hyperscribe.libraries import implemented_commands

class DummyCache:
    def current_medications(self):
        return []

    def current_conditions(self):
        return []

    def current_allergies(self):
        return []

    def current_goals(self):
        return []

    def current_tasks(self):
        return []

    def current_referrals(self):
        return []

    def current_lab_orders(self):
        return []

    def current_imaging_orders(self):
        return []

    def current_prescriptions(self):
        return []

    def current_vitals(self):
        return []
    
class DummySettings:
    @property
    def structured_rfv(self):
        return False
    @property
    def enable_smart_instructions(self):
        return False
    @property
    def enable_goal_tracking(self):
        return False
    @property
    def enable_advanced_review(self):
        return False
    @property
    def enable_allergy_tracking(self):
        return False
    @property
    def enable_medication_tracking(self):
        return False


def main(output_file_path: str):
    result = {}

    dummy_settings = DummySettings()
    dummy_cache = DummyCache()
    dummy_id = "dummy-id"

    fallback_descriptions = {
        'PhysicalExam': 'Command for documenting the physical examination findings of the patient.',
        'Questionnaire': 'Command for recording patient responses to structured or unstructured questionnaires.',
        'ReviewOfSystem': 'Command for documenting a systematic review of organ systems as reported by the patient.',
        'StructuredAssessment': 'Command for capturing structured clinical assessments, such as risk scores or screening tools.'
    }
    print(len(implemented_commands.ImplementedCommands.command_list()))
    for command_class in implemented_commands.ImplementedCommands.command_list():
        try:
            instance = command_class(dummy_settings, dummy_cache, dummy_id)
            command_name = command_class.class_name()
            description = instance.instruction_description()
            result[command_name] = description

        except Exception as e:
            command_name = command_class.class_name()
            if command_name in fallback_descriptions:
                print(f"Handled {command_name} with fallback description.")
                result[command_name] = fallback_descriptions[command_name]
            else:
                print(f"Warning: Failed to process {command_class}: {e}")

    with open(output_file_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"Wrote {len(result)} command descriptions to {output_file_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python instructions_json_generator.py <output_json_file>")
        sys.exit(1)

    output_file = sys.argv[1]
    main(output_file)
