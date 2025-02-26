from typing import Type

from commander.protocols.commands.allergy import Allergy
from commander.protocols.commands.assess import Assess
from commander.protocols.commands.base import Base
from commander.protocols.commands.close_goal import CloseGoal
from commander.protocols.commands.diagnose import Diagnose
from commander.protocols.commands.family_history import FamilyHistory
from commander.protocols.commands.follow_up import FollowUp
from commander.protocols.commands.goal import Goal
from commander.protocols.commands.history_of_present_illness import HistoryOfPresentIllness
from commander.protocols.commands.imaging_order import ImagingOrder
from commander.protocols.commands.immunize import Immunize
from commander.protocols.commands.instruct import Instruct
from commander.protocols.commands.lab_order import LabOrder
from commander.protocols.commands.medical_history import MedicalHistory
from commander.protocols.commands.medication import Medication
from commander.protocols.commands.physical_exam import PhysicalExam
from commander.protocols.commands.plan import Plan
from commander.protocols.commands.prescription import Prescription
from commander.protocols.commands.questionnaire import Questionnaire
from commander.protocols.commands.reason_for_visit import ReasonForVisit
from commander.protocols.commands.refill import Refill
from commander.protocols.commands.remove_allergy import RemoveAllergy
from commander.protocols.commands.stop_medication import StopMedication
from commander.protocols.commands.surgery_history import SurgeryHistory
from commander.protocols.commands.task import Task
from commander.protocols.commands.update_diagnose import UpdateDiagnose
from commander.protocols.commands.update_goal import UpdateGoal
from commander.protocols.commands.vitals import Vitals


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
