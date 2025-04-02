from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.handlers.implemented_commands import ImplementedCommands


def test_implemented_commands():
    tested = ImplementedCommands
    result = tested.command_list()
    for command in result:
        assert issubclass(command, Base)
    commands = [c.class_name() for c in result]
    expected = [
        'AdjustPrescription',
        'Allergy',
        'Assess',
        'CloseGoal',
        'Diagnose',
        'FamilyHistory',
        'FollowUp',
        'Goal',
        'HistoryOfPresentIllness',
        'ImagingOrder',
        'Immunize',
        'Instruct',
        'LabOrder',
        'MedicalHistory',
        'Medication',
        'Perform',
        'PhysicalExam',
        'Plan',
        'Prescription',
        'Questionnaire',
        'ReasonForVisit',
        'Refer',
        'Refill',
        'RemoveAllergy',
        'ResolveCondition',
        'ReviewOfSystem',
        'StopMedication',
        'StructuredAssessment',
        'SurgeryHistory',
        'Task',
        'UpdateDiagnose',
        'UpdateGoal',
        'Vitals',
    ]
    assert commands == expected


def test_schema_key2instruction():
    tested = ImplementedCommands
    result = tested.schema_key2instruction()
    expected = {
        'adjustPrescription': 'AdjustPrescription',
        'allergy': 'Allergy',
        'assess': 'Assess',
        'closeGoal': 'CloseGoal',
        'diagnose': 'Diagnose',
        'exam': 'PhysicalExam',
        'familyHistory': 'FamilyHistory',
        'followUp': 'FollowUp',
        'goal': 'Goal',
        'hpi': 'HistoryOfPresentIllness',
        'imagingOrder': 'ImagingOrder',
        'immunize': 'Immunize',
        'instruct': 'Instruct',
        'labOrder': 'LabOrder',
        'medicalHistory': 'MedicalHistory',
        'medicationStatement': 'Medication',
        'perform': 'Perform',
        'plan': 'Plan',
        'prescribe': 'Prescription',
        'questionnaire': 'Questionnaire',
        'reasonForVisit': 'ReasonForVisit',
        'refer': 'Refer',
        'refill': 'Refill',
        'removeAllergy': 'RemoveAllergy',
        'resolveCondition': 'ResolveCondition',
        'ros': 'ReviewOfSystem',
        'stopMedication': 'StopMedication',
        'structuredAssessment': 'StructuredAssessment',
        'surgicalHistory': 'SurgeryHistory',
        'task': 'Task',
        'updateDiagnosis': 'UpdateDiagnose',
        'updateGoal': 'UpdateGoal',
        'vitals': 'Vitals',
    }
    assert result == expected
