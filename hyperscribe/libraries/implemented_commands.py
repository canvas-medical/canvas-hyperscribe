from typing import Type

from hyperscribe.commands.adjust_prescription import AdjustPrescription
from hyperscribe.commands.allergy import Allergy
from hyperscribe.commands.assess import Assess
from hyperscribe.commands.base import Base
from hyperscribe.commands.close_goal import CloseGoal
from hyperscribe.commands.diagnose import Diagnose
from hyperscribe.commands.family_history import FamilyHistory
from hyperscribe.commands.follow_up import FollowUp
from hyperscribe.commands.goal import Goal
from hyperscribe.commands.history_of_present_illness import HistoryOfPresentIllness
from hyperscribe.commands.imaging_order import ImagingOrder
from hyperscribe.commands.immunization_statement import ImmunizationStatement
from hyperscribe.commands.immunize import Immunize
from hyperscribe.commands.instruct import Instruct
from hyperscribe.commands.lab_order import LabOrder
from hyperscribe.commands.medical_history import MedicalHistory
from hyperscribe.commands.medication import Medication
from hyperscribe.commands.perform import Perform
from hyperscribe.commands.physical_exam import PhysicalExam
from hyperscribe.commands.plan import Plan
from hyperscribe.commands.prescription import Prescription
from hyperscribe.commands.questionnaire import Questionnaire
from hyperscribe.commands.reason_for_visit import ReasonForVisit
from hyperscribe.commands.refer import Refer
from hyperscribe.commands.refill import Refill
from hyperscribe.commands.remove_allergy import RemoveAllergy
from hyperscribe.commands.resolve_condition import ResolveCondition
from hyperscribe.commands.review_of_system import ReviewOfSystem
from hyperscribe.commands.stop_medication import StopMedication
from hyperscribe.commands.structured_assessment import StructuredAssessment
from hyperscribe.commands.surgery_history import SurgeryHistory
from hyperscribe.commands.task import Task
from hyperscribe.commands.update_diagnose import UpdateDiagnose
from hyperscribe.commands.update_goal import UpdateGoal
from hyperscribe.commands.vitals import Vitals


class ImplementedCommands:
    @classmethod
    def pre_initialized(cls) -> list[Type[Base]]:
        return [
            HistoryOfPresentIllness,
            ReasonForVisit,
            PhysicalExam,
            Questionnaire,
            ReviewOfSystem,
            StructuredAssessment,
        ]

    @classmethod
    def questionnaire_command_name_list(cls) -> list[str]:
        return [c.class_name() for c in [PhysicalExam, Questionnaire, ReviewOfSystem, StructuredAssessment]]

    @classmethod
    def command_list(cls) -> list[Type[Base]]:
        return [
            AdjustPrescription,
            Allergy,
            Assess,
            CloseGoal,
            Diagnose,
            FamilyHistory,
            FollowUp,
            Goal,
            HistoryOfPresentIllness,
            ImagingOrder,
            ImmunizationStatement,
            Immunize,
            Instruct,
            LabOrder,
            MedicalHistory,
            Medication,
            Perform,
            PhysicalExam,
            Plan,
            Prescription,
            Questionnaire,
            ReasonForVisit,
            Refer,
            Refill,
            RemoveAllergy,
            ResolveCondition,
            ReviewOfSystem,
            StopMedication,
            StructuredAssessment,
            SurgeryHistory,
            Task,
            UpdateDiagnose,
            UpdateGoal,
            Vitals,
        ]

    @classmethod
    def schema_key2instruction(cls) -> dict[str, str]:
        return {command_class.schema_key(): command_class.class_name() for command_class in cls.command_list()}
