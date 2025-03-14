from typing import Type

from hyperscribe.handlers.commands.adjust_prescription import AdjustPrescription
from hyperscribe.handlers.commands.allergy import Allergy
from hyperscribe.handlers.commands.assess import Assess
from hyperscribe.handlers.commands.base import Base
from hyperscribe.handlers.commands.close_goal import CloseGoal
from hyperscribe.handlers.commands.diagnose import Diagnose
from hyperscribe.handlers.commands.family_history import FamilyHistory
from hyperscribe.handlers.commands.follow_up import FollowUp
from hyperscribe.handlers.commands.goal import Goal
from hyperscribe.handlers.commands.history_of_present_illness import HistoryOfPresentIllness
from hyperscribe.handlers.commands.imaging_order import ImagingOrder
from hyperscribe.handlers.commands.immunize import Immunize
from hyperscribe.handlers.commands.instruct import Instruct
from hyperscribe.handlers.commands.lab_order import LabOrder
from hyperscribe.handlers.commands.medical_history import MedicalHistory
from hyperscribe.handlers.commands.medication import Medication
from hyperscribe.handlers.commands.perform import Perform
from hyperscribe.handlers.commands.physical_exam import PhysicalExam
from hyperscribe.handlers.commands.plan import Plan
from hyperscribe.handlers.commands.prescription import Prescription
from hyperscribe.handlers.commands.questionnaire import Questionnaire
from hyperscribe.handlers.commands.reason_for_visit import ReasonForVisit
from hyperscribe.handlers.commands.refer import Refer
from hyperscribe.handlers.commands.refill import Refill
from hyperscribe.handlers.commands.remove_allergy import RemoveAllergy
from hyperscribe.handlers.commands.resolve_condition import ResolveCondition
from hyperscribe.handlers.commands.review_of_system import ReviewOfSystem
from hyperscribe.handlers.commands.stop_medication import StopMedication
from hyperscribe.handlers.commands.structured_assessment import StructuredAssessment
from hyperscribe.handlers.commands.surgery_history import SurgeryHistory
from hyperscribe.handlers.commands.task import Task
from hyperscribe.handlers.commands.update_diagnose import UpdateDiagnose
from hyperscribe.handlers.commands.update_goal import UpdateGoal
from hyperscribe.handlers.commands.vitals import Vitals


class ImplementedCommands:

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
        return {
            command_class.schema_key(): command_class.class_name()
            for command_class in cls.command_list()
        }
