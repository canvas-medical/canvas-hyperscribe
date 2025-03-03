from typing import Type

from hyperscribe.protocols.commands.allergy import Allergy
from hyperscribe.protocols.commands.assess import Assess
from hyperscribe.protocols.commands.base import Base
from hyperscribe.protocols.commands.close_goal import CloseGoal
from hyperscribe.protocols.commands.diagnose import Diagnose
from hyperscribe.protocols.commands.family_history import FamilyHistory
from hyperscribe.protocols.commands.follow_up import FollowUp
from hyperscribe.protocols.commands.goal import Goal
from hyperscribe.protocols.commands.history_of_present_illness import HistoryOfPresentIllness
from hyperscribe.protocols.commands.imaging_order import ImagingOrder
from hyperscribe.protocols.commands.immunize import Immunize
from hyperscribe.protocols.commands.instruct import Instruct
from hyperscribe.protocols.commands.lab_order import LabOrder
from hyperscribe.protocols.commands.medical_history import MedicalHistory
from hyperscribe.protocols.commands.medication import Medication
from hyperscribe.protocols.commands.physical_exam import PhysicalExam
from hyperscribe.protocols.commands.plan import Plan
from hyperscribe.protocols.commands.prescription import Prescription
from hyperscribe.protocols.commands.questionnaire import Questionnaire
from hyperscribe.protocols.commands.reason_for_visit import ReasonForVisit
from hyperscribe.protocols.commands.refill import Refill
from hyperscribe.protocols.commands.remove_allergy import RemoveAllergy
from hyperscribe.protocols.commands.stop_medication import StopMedication
from hyperscribe.protocols.commands.surgery_history import SurgeryHistory
from hyperscribe.protocols.commands.task import Task
from hyperscribe.protocols.commands.update_diagnose import UpdateDiagnose
from hyperscribe.protocols.commands.update_goal import UpdateGoal
from hyperscribe.protocols.commands.vitals import Vitals


class ImplementedCommands:

    @classmethod
    def command_list(cls) -> list[Type[Base]]:
        return [
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
            PhysicalExam,
            Plan,
            Prescription,
            Questionnaire,
            ReasonForVisit,
            Refill,
            RemoveAllergy,
            StopMedication,
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
