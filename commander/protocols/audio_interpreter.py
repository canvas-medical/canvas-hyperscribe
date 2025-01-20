import json
from datetime import datetime
from typing import Type

from canvas_sdk.commands.base import _BaseCommand as BaseCommand

from commander.protocols.constants import Constants
from commander.protocols.openai_chat import OpenaiChat
from commander.protocols.structures.commands.allergy import Allergy
from commander.protocols.structures.commands.assess import Assess
from commander.protocols.structures.commands.base import Base
from commander.protocols.structures.commands.close_goal import CloseGoal
from commander.protocols.structures.commands.diagnose import Diagnose
from commander.protocols.structures.commands.family_history import FamilyHistory
from commander.protocols.structures.commands.goal import Goal
from commander.protocols.structures.commands.history_of_present_illness import HistoryOfPresentIllness
from commander.protocols.structures.commands.immunize import Immunize
from commander.protocols.structures.commands.instruct import Instruct
from commander.protocols.structures.commands.lab_order import LabOrder
from commander.protocols.structures.commands.medical_history import MedicalHistory
from commander.protocols.structures.commands.medication import Medication
from commander.protocols.structures.commands.physical_exam import PhysicalExam
from commander.protocols.structures.commands.plan import Plan
from commander.protocols.structures.commands.prescription import Prescription
from commander.protocols.structures.commands.questionnaire import Questionnaire
from commander.protocols.structures.commands.reason_for_visit import ReasonForVisit
from commander.protocols.structures.commands.refill import Refill
from commander.protocols.structures.commands.remove_allergy import RemoveAllergy
from commander.protocols.structures.commands.stop_medication import StopMedication
from commander.protocols.structures.commands.surgery_history import SurgeryHistory
from commander.protocols.structures.commands.task import Task
from commander.protocols.structures.commands.update_diagnose import UpdateDiagnose
from commander.protocols.structures.commands.update_goal import UpdateGoal
from commander.protocols.structures.commands.vitals import Vitals
from commander.protocols.structures.instruction import Instruction
from commander.protocols.structures.json_extract import JsonExtract
from commander.protocols.structures.line import Line
from commander.protocols.structures.settings import Settings


class AudioInterpreter:

    def __init__(self, settings: Settings, patient_id: str, note_uuid: str, provider_uuid: str) -> None:
        self.settings = settings
        self.patient_id = patient_id
        self.note_uuid = note_uuid
        self._command_context = [
            command_class(settings, patient_id, note_uuid, provider_uuid)
            for command_class in self.implemented_commands()
        ]

    def instruction_definitions(self) -> list[dict[str, str]]:
        return [
            {
                "instruction": instance.class_name(),
                "information": instance.instruction_description(),
            }
            for instance in self._command_context if instance.is_available()
        ]

    def instruction_constraints(self) -> list[str]:
        result: list[str] = []
        for instance in self._command_context:
            if instance.is_available() and (constraint := instance.instruction_constraints()):
                result.append(constraint)
        return result

    def command_structures(self) -> dict:
        return {
            instance.class_name(): instance.command_parameters()
            for instance in self._command_context if instance.is_available()
        }

    def combine_and_speaker_detection(self, audio_chunks: list[bytes]) -> JsonExtract:
        conversation = OpenaiChat(self.settings.openai_key, Constants.OPENAI_CHAT_AUDIO)
        conversation.system_prompt = [
            "The conversation is in the medical context.",
            "",
            "Your task is to identify the speakers and report what they say.",
            "",
        ]
        conversation.user_prompt = [
            'These audio files contain recordings of a single conversation, segmented into overlapping parts. '
            'Each file has approximately 5 seconds of overlap with both the preceding and following segments.',
            '',
            'The conversation takes place in a medical setting, specifically during a patient\'s visit to a healthcare provider.',
            '',
            'Your task is to:',
            '1. Identify the speakers in the conversation',
            '2. Transcribe what each person says',
            '',
            'Please present your findings in a JSON format within a Markdown code block. '
            'Each entry in the JSON should be an object with two keys:',
            '- "speaker": to identify who is talking (e.g., "Patient", "Doctor", "Nurse"...)',
            '- "text": the verbatim transcription of what the speaker said',
            '',
        ]
        extension = "webm"
        for audio in audio_chunks:
            conversation.add_audio(audio, extension)
        return conversation.chat()

    def detect_instructions(self, discussion: list[Line], known_instructions: list[Instruction]) -> JsonExtract:
        conversation = OpenaiChat(self.settings.openai_key, Constants.OPENAI_CHAT_TEXT)
        conversation.system_prompt = [
            "The conversation is in the medical context.",
            "The user will submit the transcript of the visit of a patient with a healthcare provider.",
            "The user needs to extract and store the relevant information in their software using several commands as described below.",
            "Your task is to help the user by identifying the instructions and the linked information, regardless of their location in the transcript.",
            "",
            "The instructions are limited to:",
            "```json",
            json.dumps(self.instruction_definitions()),
            "```",
            "",
            'Your response has to be a JSON Markdown block with a list of objects: {'
            '"uuid": "a unique identifier in this discussion", '
            '"instruction": "the instruction", '
            '"information": "any information related to the instruction"},',
            "",
            "The JSON will be validated with the schema:",
            "```json",
            json.dumps(self.json_schema([instance.class_name() for instance in self._command_context])),
            "```",
            "",
        ]
        transcript = json.dumps([speaker.to_json() for speaker in discussion], indent=1)
        conversation.user_prompt = [
            "Below is a part of the transcript of the visit of a patient with a healthcare provider.",
            "What are the instructions I need to add to my software to correctly record the visit?",
            "```json",
            transcript,
            "```",
            "",
        ]
        if known_instructions:
            content = json.dumps([instruction.to_json() for instruction in known_instructions], indent=1)
            conversation.user_prompt.extend([
                "From previous parts of the transcript, the following instructions were identified",
                "```json",
                content,
                "```",
                "Include them in your response, with any necessary additional information.",
            ])
        result = conversation.chat()
        if result.has_error is False and (constraints := self.instruction_constraints()):
            conversation.user_prompt = [
                "Here is your last response:",
                "```json",
                json.dumps(result.content, indent=1),
                "```",
                "",
                "Review your response and be sure to follow these constraints:",
            ]
            for constraint in constraints:
                conversation.user_prompt.append(f" * {constraint}")
            conversation.user_prompt.append("")
            conversation.user_prompt.append("Return the original JSON if valid, or provide a corrected version to follow the constraints if needed.")
            conversation.user_prompt.append("")
            result = conversation.chat()
        return result

    def create_sdk_commands(self, known_instructions: list[Instruction]) -> list[tuple[Instruction, dict]]:
        result: list[tuple[Instruction, dict]] = []

        structures = self.command_structures()

        conversation = OpenaiChat(self.settings.openai_key, Constants.OPENAI_CHAT_TEXT)
        conversation.system_prompt = [
            "The conversation is in the medical context.",
            "During a visit of a patient with a healthcare provider, the user has identified instructions to record in its software.",
            "The user will submit an instruction, i.e. an action and the related information, as well as the structure of the associated command.",
            "Your task is to help the user by identifying the actual data of the structured command.",
            "",
            "Your response has to be a JSON Markdown block encapsulating the filled structure.",
            "",
            f"Please, note that now is {datetime.now().isoformat()}."
        ]
        for instruction in known_instructions:
            conversation.user_prompt = [
                "Based on the text:",
                "```text",
                instruction.information,
                "```",
                "",
                "Your task is to replace the values of the JSON object with the relevant information:",
                "```json",
                json.dumps([structures[instruction.instruction]], indent=1),
                "```",
                "",
            ]
            response = conversation.chat()
            if response.has_error is False:
                result.append((instruction, response.content[0]))
        return result

    def create_command_from(self, instruction: Instruction, parameters: dict) -> BaseCommand | None:
        for instance in self._command_context:
            if instruction.instruction == instance.class_name():
                return instance.command_from_json(parameters)
        return None

    @classmethod
    def json_schema(cls, commands: list[str]) -> dict:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "uuid": {"type": "string", "description": "a unique identifier in this discussion"},
                    "instruction": {
                        "type": "string",
                        "enum": commands,
                    },
                    "information": {"type": "string",
                                    "description": "all relevant information extracted from the discussion explaining and/or defining the instruction"},
                },
                "required": ["uuid", "instruction", "information"],
                "additionalProperties": False,
            }
        }

    @classmethod
    def implemented_commands(cls) -> list[Type[Base]]:
        return [
            Allergy,
            Assess,
            CloseGoal,
            Diagnose,
            FamilyHistory,
            Goal,
            HistoryOfPresentIllness,
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
