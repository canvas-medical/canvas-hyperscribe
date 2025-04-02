from typing import Type

from hyperscribe_tuning.commands.adjust_prescription import AdjustPrescription
from hyperscribe_tuning.commands.allergy import Allergy
from hyperscribe_tuning.commands.assess import Assess
from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.close_goal import CloseGoal
from hyperscribe_tuning.commands.diagnose import Diagnose
from hyperscribe_tuning.commands.family_history import FamilyHistory
from hyperscribe_tuning.commands.follow_up import FollowUp
from hyperscribe_tuning.commands.goal import Goal
from hyperscribe_tuning.commands.history_of_present_illness import HistoryOfPresentIllness
from hyperscribe_tuning.commands.imaging_order import ImagingOrder
from hyperscribe_tuning.commands.immunize import Immunize
from hyperscribe_tuning.commands.instruct import Instruct
from hyperscribe_tuning.commands.lab_order import LabOrder
from hyperscribe_tuning.commands.medical_history import MedicalHistory
from hyperscribe_tuning.commands.medication import Medication
from hyperscribe_tuning.commands.perform import Perform
from hyperscribe_tuning.commands.physical_exam import PhysicalExam
from hyperscribe_tuning.commands.plan import Plan
from hyperscribe_tuning.commands.prescription import Prescription
from hyperscribe_tuning.commands.questionnaire import Questionnaire
from hyperscribe_tuning.commands.reason_for_visit import ReasonForVisit
from hyperscribe_tuning.commands.refer import Refer
from hyperscribe_tuning.commands.refill import Refill
from hyperscribe_tuning.commands.remove_allergy import RemoveAllergy
from hyperscribe_tuning.commands.resolve_condition import ResolveCondition
from hyperscribe_tuning.commands.review_of_system import ReviewOfSystem
from hyperscribe_tuning.commands.stop_medication import StopMedication
from hyperscribe_tuning.commands.structured_assessment import StructuredAssessment
from hyperscribe_tuning.commands.surgery_history import SurgeryHistory
from hyperscribe_tuning.commands.task import Task
from hyperscribe_tuning.commands.update_diagnose import UpdateDiagnose
from hyperscribe_tuning.commands.update_goal import UpdateGoal
from hyperscribe_tuning.commands.vitals import Vitals


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
