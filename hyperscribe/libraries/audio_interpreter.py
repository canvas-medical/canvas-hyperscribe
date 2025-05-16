import json
from datetime import datetime

from hyperscribe.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe.handlers.progress import Progress
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.json_extract import JsonExtract
from hyperscribe.structures.line import Line
from hyperscribe.structures.settings import Settings


class AudioInterpreter:

    def __init__(
            self,
            settings: Settings,
            s3_credentials: AwsS3Credentials,
            cache: LimitedCache,
            identification: IdentificationParameters,
    ) -> None:
        self.settings = settings
        self.s3_credentials = s3_credentials
        self.identification = identification
        self._command_context = [
            instance
            for command_class in ImplementedCommands.command_list()
            if (instance := command_class(settings, cache, identification))
               and instance.is_available()
        ]

    def instruction_definitions(self) -> list[dict[str, str]]:
        return [
            {
                "instruction": instance.class_name(),
                "information": instance.instruction_description(),
            }
            for instance in self._command_context
            if instance.class_name() not in ImplementedCommands.questionnaire_command_name_list()
        ]

    def instruction_constraints(self, instructions: list[Instruction]) -> list[str]:
        result: list[str] = []
        names = [i.instruction for i in instructions]
        for instance in self._command_context:
            if instance.class_name() in names and (constraint := instance.instruction_constraints()):
                result.append(constraint)
        return result

    def command_structures(self) -> dict:
        return {
            instance.class_name(): instance.command_parameters()
            for instance in self._command_context
            if instance.class_name() not in ImplementedCommands.questionnaire_command_name_list()
        }

    def combine_and_speaker_detection(self, audio_chunks: list[bytes], transcript_tail: str) -> JsonExtract:
        conversation = Helper.audio2texter(
            self.settings,
            MemoryLog.instance(self.identification, "audio2transcript", self.s3_credentials),
        )
        conversation.set_system_prompt([
            "The conversation is in the medical context, and related to a visit of a patient with a healthcare provider.",
            "",
            "Your task is to transcribe what was said, regardless of whether the audio recordings were of dialogue during the visit or monologue after the visit.",
            "",
        ])
        previous_transcript = ""
        if transcript_tail:
            previous_transcript = f"\nThe previous segment finished with: '{transcript_tail}'.\n"
        conversation.set_user_prompt([
            "The recording takes place in a medical setting, specifically related to a patient's visit with a clinician.",
            "",
            "These audio files contain recordings of a single visit.",
            "There is no overlap between the segments, so they should be regarded as a continuous flow and analyzed at once.",
            previous_transcript,
            'Your task is to:',
            "1. label each voice if multiple voices are present.",
            "2. transcribe each speaker's words with maximum accuracy.",
            "",
            "Present your findings in a JSON format within a Markdown code block:",
            "```json",
            json.dumps([
                {
                    "voice": "voice_1/voice_2/.../voice_N",
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
                    "voice": "voice_1/voice_2/.../voice_N",
                }
            ], indent=1),
            "```",
            "",
        ])

        extension = "mp3"
        for audio in audio_chunks:
            conversation.add_audio(audio, extension)

        response = conversation.chat(JsonSchema.get(["voice_split", "voice_identification"]))
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
        schema = self.json_schema(
            [instance.class_name() for instance in self._command_context]
        )
        system_prompt = [
            "The conversation is in the context of a clinical encounter between patient and licensed healthcare provider.",
            "The user will submit the transcript of the visit of a patient with the healthcare provider.",
            "The user needs to extract and store the relevant information in their software using structured commands as described below.",
            "Your task is to help the user by identifying the relevant instructions and their linked information, regardless of their location in the transcript.",
            "If any portion of the transcript is small talk, chit chat, or side bar with no discernible connection to health concerns, then it should be ignored."
            "",
            "The instructions are limited to the following:",
            "```json",
            json.dumps(self.instruction_definitions()),
            "```",
            "",
            "Your response must be a JSON Markdown block validated with the schema:",
            "```json",
            json.dumps(schema),
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
            content = [instruction.to_json(True) for instruction in known_instructions]
            user_prompt.extend([
                "From among all previous segments of the transcript, the following instructions were identified:",
                "```json",
                json.dumps(content, indent=1),
                "```",
                "It is important to include them in your response, with any necessary additional information mentioned in the transcript.",
            ])
        chatter = Helper.chatter(
            self.settings,
            MemoryLog.instance(self.identification, "transcript2instructions", self.s3_credentials),
        )
        result = chatter.single_conversation(system_prompt, user_prompt, [schema], None)

        # limit the constraints to the reported instructions only
        instructions = Instruction.load_from_json(result)
        if result and (constraints := self.instruction_constraints(instructions)):
            chatter.set_model_prompt(["```json", json.dumps(result), "```"])
            user_prompt = [
                "Review your response and be sure to follow these constraints:",
            ]
            for constraint in constraints:
                user_prompt.append(f" * {constraint}")
            user_prompt.append("")
            user_prompt.append("Return the original JSON if valid, or provide a corrected version to follow the constraints if needed.")
            user_prompt.append("")
            result = chatter.single_conversation(system_prompt, user_prompt, [schema], None)
        return result

    def create_sdk_command_parameters(self, instruction: Instruction) -> InstructionWithParameters | None:
        result: InstructionWithParameters | None = None

        structures = self.command_structures()

        system_prompt = [
            "The conversation is in the context of a clinical encounter between patient and licensed healthcare provider.",
            "During the encounter, the user has identified instructions with key information to record in its software.",
            "The user will submit an instruction and the linked information grounded in the transcript, as well as the structure of the associated command.",
            "Your task is to help the user by writing correctly detailed data for the structured command.",
            "Unless explicitly instructed otherwise for a specific command, you must not make up or refer to any details of any kind that are not explicitly present in the transcript or prior instructions.",
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
        log_label = f"{instruction.instruction}_{instruction.uuid}_instruction2parameters"
        memory_log = MemoryLog.instance(self.identification, log_label, self.s3_credentials)
        chatter = Helper.chatter(self.settings, memory_log)
        schemas = JsonSchema.get(["generic_parameters"])
        response = chatter.single_conversation(system_prompt, user_prompt, schemas, instruction)
        if response:
            result = InstructionWithParameters.add_parameters(instruction, response[0])
        if result:
            Progress.send_to_user(self.identification, self.settings, f"parameters identified for {instruction.instruction}")
        return result

    def create_sdk_command_from(self, direction: InstructionWithParameters) -> InstructionWithCommand | None:
        for instance in self._command_context:
            if direction.instruction == instance.class_name():
                log_label = f"{direction.instruction}_{direction.uuid}_parameters2command"
                memory_log = MemoryLog.instance(self.identification, log_label, self.s3_credentials)
                chatter = Helper.chatter(self.settings, memory_log)
                result = instance.command_from_json(direction, chatter)
                if result:
                    Progress.send_to_user(self.identification, self.settings, f"command generated for {direction.instruction}")
                return result
        return None

    def update_questionnaire(self, discussion: list[Line], direction: Instruction) -> InstructionWithCommand | None:
        for instance in self._command_context:
            if direction.instruction == instance.class_name():
                # assert isinstance(instance, BaseQuestionnaire)
                log_label = f"{direction.instruction}_{direction.uuid}_questionnaire_update"
                chatter = Helper.chatter(
                    self.settings,
                    MemoryLog.instance(self.identification, log_label, self.s3_credentials),
                )
                questionnaire = instance.update_from_transcript(discussion, direction, chatter)
                command = instance.command_from_questionnaire(direction.uuid, questionnaire)
                return InstructionWithCommand(
                    uuid=direction.uuid,
                    index=direction.index,
                    instruction=direction.instruction,
                    information=json.dumps(questionnaire.to_json()),
                    is_new=False,
                    is_updated=True,
                    parameters={},
                    command=command,
                )
        return None

    @classmethod
    def json_schema(cls, commands: list[str]) -> dict:
        properties = {
            "uuid": {
                "type": "string",
                "description": "a unique identifier in this discussion",
            },
            "index": {
                "type": "integer",
                "description": "the 0-based appearance order of the instruction in this discussion",
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
        required = ["uuid", "index", "instruction", "information", "isNew", "isUpdated"]

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
