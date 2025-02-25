import json
from datetime import datetime
from typing import Type

from canvas_sdk.commands.base import _BaseCommand as BaseCommand

from commander.protocols.commands.allergy import Allergy
from commander.protocols.commands.assess import Assess
from commander.protocols.commands.base import Base
from commander.protocols.commands.close_goal import CloseGoal
from commander.protocols.commands.diagnose import Diagnose
from commander.protocols.commands.family_history import FamilyHistory
from commander.protocols.commands.follow_up import FollowUp
from commander.protocols.commands.goal import Goal
from commander.protocols.commands.history_of_present_illness import HistoryOfPresentIllness
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
from commander.protocols.helper import Helper
from commander.protocols.limited_cache import LimitedCache
from commander.protocols.structures.instruction import Instruction
from commander.protocols.structures.json_extract import JsonExtract
from commander.protocols.structures.line import Line
from commander.protocols.structures.settings import Settings


class AudioInterpreter:

    def __init__(self, settings: Settings, cache: LimitedCache, patient_id: str, note_uuid: str, provider_uuid: str) -> None:
        self.settings = settings
        self.patient_id = patient_id
        self.note_uuid = note_uuid
        self._command_context = [
            instance
            for command_class in self.implemented_commands()
            if (instance := command_class(settings, cache, patient_id, note_uuid, provider_uuid))
               and instance.is_available()
        ]

    def instruction_definitions(self) -> list[dict[str, str]]:
        return [
            {
                "instruction": instance.class_name(),
                "information": instance.instruction_description(),
            }
            for instance in self._command_context
        ]

    def instruction_constraints(self) -> list[str]:
        result: list[str] = []
        for instance in self._command_context:
            if constraint := instance.instruction_constraints():
                result.append(constraint)
        return result

    def command_structures(self) -> dict:
        return {
            instance.class_name(): instance.command_parameters()
            for instance in self._command_context
        }

    def combine_and_speaker_detection(self, audio_chunks: list[bytes]) -> JsonExtract:
        conversation = Helper.audio2texter(self.settings)
        conversation.set_system_prompt([
            "The conversation is in the medical context, and related to a visit of a patient with a healthcare provider.",
            "",
            "Your task is to transcribe what was said, regardless of whether the audio recordings were of dialogue during the visit or monologue after the visit.",
            "",
        ])
        conversation.set_user_prompt([
            "The recording takes place in a medical setting, specifically related to a patient's visit with a clinician.",
            "",
            "These audio files contain recordings of a single visit.",
            "There is no overlap between the segments, so they should be regarded as a continuous flow and analyzed at once.",
            "",
            'Your task is to:',
            "1. label each voice if multiple voices are present.",
            "2. transcribe each speaker's words with maximum accuracy",
            "",
            "Present your findings in a JSON format within a Markdown code block:",
            "```json",
            json.dumps([
                {
                    "voice": "voice_X/voice_Y/.../voice_N",
                    "text": "the verbatim transcription of what the speaker said",
                }
            ], indent=1),
            "```",
            "",
            "Then, review the discussion from the top and distinguish the role of the voices (patient, clinician, nurse, parents...) in the conversation, if there is only voice, assume this is the clinician",
            "",
            "Present your findings in a JSON format within a Markdown code block:",
            "```json",
            json.dumps([
                {
                    "speaker": "Patient/Clinician/Nurse/...",
                    "voice": "voice_A/voice_B/.../voice_N",
                }
            ], indent=1),
            "```",
            "",
        ])

        extension = "mp3"
        for audio in audio_chunks:
            conversation.add_audio(audio, extension)
        response = conversation.chat(True)
        if response.has_error:
            return response
        if len(response.content) < 2:
            return JsonExtract(
                has_error=True,
                error="partial response",
                content=response.content,
            )

        discussion = response.content[0]
        speakers = {
            speaker["voice"]: speaker["speaker"]
            for speaker in response.content[1]
        }
        return JsonExtract(
            has_error=False,
            error="",
            content=[
                {
                    "speaker": speakers[text["voice"]],
                    "text": text["text"],
                }
                for text in discussion
            ],
        )

    def detect_instructions(self, discussion: list[Line], known_instructions: list[Instruction]) -> list:
        example = {
            "uuid": "a unique identifier in this discussion",
            "instruction": "the instruction",
            "information": "the information associated with the instruction, grounded in the transcript with no embellishment or omission",
            "isNew": "the instruction is new for the discussion, as boolean",
            "isUpdated": "the instruction is an update of one already identified in the discussion, as boolean",
        }

        system_prompt = [
            "The conversation is in the context of a clinical encounter between patient and licensed healthcare provider.",
            "The user will submit the transcript of the visit of a patient with the healthcare provider.",
            "The user needs to extract and store the relevant information in their software using structured commands as described below.",
            "Your task is to help the user by identifying the relevant instructions and their linked information, regardless of their location in the transcript.",
            "If any portion of the transcript is small talk, chit chat, or side bar with no discernable connection to health concerns, then it should be ignored."
            "",
            "The instructions are limited to the following:",
            "```json",
            json.dumps(self.instruction_definitions()),
            "```",
            "",
            'Your response must be a JSON Markdown block with a list of objects: ',
            json.dumps(example),
            "",
            "The JSON will be validated with the schema:",
            "```json",
            json.dumps(self.json_schema([instance.class_name() for instance in self._command_context])),
            "```",
            "",
        ]
        transcript = json.dumps([speaker.to_json() for speaker in discussion], indent=1)
        user_prompt = [
            "Below is the most recent segment of the transcript of the visit of a patient with a healthcare provider.",
            "What are the instructions I need to add to my software to document the visit correctly?",
            "```json",
            transcript,
            "```",
            "",
        ]
        if known_instructions:
            content = json.dumps([instruction.to_json() for instruction in known_instructions], indent=1)
            user_prompt.extend([
                "From among all previous segments of the transcript, the following instructions were identified",
                "```json",
                content,
                "```",
                "Include them in your response, with any necessary additional information.",
            ])
        result = Helper.chatter(self.settings).single_conversation(system_prompt, user_prompt)
        if result and (constraints := self.instruction_constraints()):
            user_prompt = [
                "Here is your last response:",
                "```json",
                json.dumps(result, indent=1),
                "```",
                "",
                "Review your response and be sure to follow these constraints:",
            ]
            for constraint in constraints:
                user_prompt.append(f" * {constraint}")
            user_prompt.append("")
            user_prompt.append("Return the original JSON if valid, or provide a corrected version to follow the constraints if needed.")
            user_prompt.append("")
            result = Helper.chatter(self.settings).single_conversation(system_prompt, user_prompt)
        return result

    def create_sdk_command_parameters(self, instruction: Instruction) -> tuple[Instruction, dict | None]:
        result: tuple[Instruction, dict | None] = instruction, None

        structures = self.command_structures()

        system_prompt = [
            "The conversation is in the context of a clinical encounter between patient and licensed healthcare provider.",
            "During the encounter, the user has identified instructions with key information to record in its software.",
            "The user will submit an instruction and the linked information grounded in the transcript, as well as the structure of the associated command.",
            "Your task is to help the user by writing correctly detailed data for the structured command.",
            "Unless explicitly instructed otherwise for a specific command, you must not make up or refer to any details of any kind ",
            "that are not explicitly present in the transcript or prior instructions.",
            "",
            "Your response has to be a JSON Markdown block encapsulating the filled structure.",
            "",
            f"Please, note that now is {datetime.now().isoformat()}."
        ]
        user_prompt = [
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
        response = Helper.chatter(self.settings).single_conversation(system_prompt, user_prompt)
        if response:
            result = instruction, response[0]
        return result

    def create_sdk_command_from(self, instruction: Instruction, parameters: dict) -> BaseCommand | None:
        for instance in self._command_context:
            if instruction.instruction == instance.class_name():
                return instance.command_from_json(parameters)
        return None

    @classmethod
    def json_schema(cls, commands: list[str]) -> dict:
        properties = {
            "uuid": {
                "type": "string",
                "description": "a unique identifier in this discussion",
            },
            "instruction": {
                "type": "string",
                "enum": commands,
            },
            "information": {
                "type": "string",
                "description": "all relevant information extracted from the discussion explaining and/or defining the instruction",
            },
            "isNew": {
                "type": "boolean",
                "description": "the instruction is new to the discussion",
            },
            "isUpdated": {
                "type": "boolean",
                "description": "the instruction is an update of an instruction previously identified in the discussion",
            },
        }
        required = ["uuid", "instruction", "information", "isNew", "isUpdated"]
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {
                "type": "object",
                "properties": properties,
                "required": required,
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
            FollowUp,
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

    @classmethod
    def schema_key2instruction(cls) -> dict[str, str]:
        return {
            command_class.schema_key(): command_class.class_name()
            for command_class in cls.implemented_commands()
        }
