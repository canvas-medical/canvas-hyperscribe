import json
from collections import defaultdict
from datetime import datetime

from hyperscribe.commands.base import Base
from hyperscribe.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe.handlers.progress_display import ProgressDisplay
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.json_extract import JsonExtract
from hyperscribe.structures.line import Line
from hyperscribe.structures.model_spec import ModelSpec
from hyperscribe.structures.progress_message import ProgressMessage
from hyperscribe.structures.section_with_transcript import SectionWithTranscript
from hyperscribe.structures.settings import Settings


class AudioInterpreter:
    def __init__(
        self,
        settings: Settings,
        s3_credentials: AwsS3Credentials,
        cache: LimitedCache,
        identification: IdentificationParameters,
    ) -> None:
        self.is_local_data = cache.is_local_data
        self.settings = settings
        self.s3_credentials = s3_credentials
        self.identification = identification
        self.cache = cache
        self._command_context = {
            instance.class_name(): instance
            for command_class in ImplementedCommands.command_list()
            if (instance := command_class(settings, cache, identification))
            and self.settings.commands_policy.is_allowed(instance.class_name())
            and instance.is_available()
        }

    def common_instructions(self) -> list[Base]:
        return [
            instance
            for class_name, instance in self._command_context.items()
            if class_name not in ImplementedCommands.questionnaire_command_name_list()
        ]

    def instruction_constraints(self, instructions: list[Instruction]) -> list[str]:
        result: list[str] = []
        names = [i.instruction for i in instructions]
        for class_name, instance in self._command_context.items():
            if class_name in names and (constraint := instance.instruction_constraints()):
                result.append(constraint)
        return result

    def command_structures(self, class_name: str) -> dict:
        if class_name in ImplementedCommands.questionnaire_command_name_list():
            raise ValueError(f"{class_name} is a questionnaire")
        if class_name not in self._command_context:
            raise ValueError(f"{class_name} is not a known command")
        return self._command_context[class_name].command_parameters()

    def command_schema(self, class_name: str) -> list[dict]:
        if class_name in ImplementedCommands.questionnaire_command_name_list():
            raise ValueError(f"{class_name} is a questionnaire")
        if class_name not in self._command_context:
            raise ValueError(f"{class_name} is not a known command")
        return self._command_context[class_name].command_parameters_schemas()

    def combine_and_speaker_detection(self, audio_bytes: bytes, transcript_tail: list[Line]) -> JsonExtract:
        memory_log = MemoryLog.instance(self.identification, "audio2transcript", self.s3_credentials)
        transcriber = Helper.audio2texter(self.settings, memory_log)
        extension = "mp3"
        transcriber.add_audio(audio_bytes, extension)

        if transcriber.support_speaker_identification():
            return self.combine_and_speaker_detection_single_step(transcriber, transcript_tail)
        else:
            memory_log = MemoryLog.instance(self.identification, "speakerDetection", self.s3_credentials)
            detector = Helper.chatter(self.settings, memory_log, ModelSpec.COMPLEX)
            return self.combine_and_speaker_detection_double_step(transcriber, detector, transcript_tail)

    @classmethod
    def combine_and_speaker_detection_double_step(
        cls,
        transcriber: LlmBase,
        detector: LlmBase,
        transcript_tail: list[Line],
    ) -> JsonExtract:
        response = transcriber.chat(JsonSchema.get([]))
        if response.has_error:
            return response
        # using the LLM text to identify the speakers
        detector.set_system_prompt(
            [
                "The conversation is in the medical context, and related to a visit of a patient with a "
                "healthcare provider.",
                "",
                "A recording is parsed in realtime and the transcription is reported for each speaker.",
                "Your task is to identify the speakers of the provided transcription.",
                "",
            ],
        )
        previous_transcript = ""
        if transcript_tail:
            previous_transcript = "\n".join(
                [
                    "The previous segment finished with:",
                    "```json",
                    json.dumps([line.to_json() for line in transcript_tail], indent=1),
                    "```",
                    "",
                ],
            )
        detector.set_user_prompt(
            [
                previous_transcript,
                "Your task is to identify the role of the voices (patient, clinician, nurse, parents...) "
                "in the conversation, if there is only one voice, or just only silence, assume this is the clinician.",
                "",
                "```json",
                json.dumps(response.content[0], indent=1),
                "```",
                "",
                "Present your findings in a JSON format within a Markdown code block:",
                "```json",
                json.dumps(
                    [
                        {
                            "speaker": "Patient/Clinician/Nurse/Parent...",
                            "text": "the verbatim transcription as reported in the transcription",
                            "start": "the start as reported in the transcription",
                            "end": "the end as reported in the transcription",
                        },
                    ],
                    indent=1,
                ),
                "```",
                "",
            ],
        )
        response = detector.chat(JsonSchema.get(["voice_turns"]))
        if response.has_error:
            return response
        return JsonExtract(has_error=False, error="", content=response.content[0])

    @classmethod
    def combine_and_speaker_detection_single_step(cls, detector: LlmBase, transcript_tail: list[Line]) -> JsonExtract:
        detector.set_system_prompt(
            [
                "The conversation is in the medical context, and related to a visit of a patient with a "
                "healthcare provider.",
                "",
                "Your task is to transcribe what was said with maximum accuracy, capturing ALL clinical"
                "information including patient symptoms, medical history, medications, treatment plans"
                "and provider recommendations.",
                "Ensure complete documentation of patient-reported concerns and clinician instructions,"
                "as missing clinical details significantly impact care quality.",
                "",
            ],
        )
        previous_transcript = ""
        if transcript_tail:
            previous_transcript = "\n".join(
                [
                    "The previous segment finished with:",
                    "```json",
                    json.dumps([line.to_json() for line in transcript_tail], indent=1),
                    "```",
                    "",
                ],
            )
        detector.set_user_prompt(
            [
                "The recording takes place in a medical setting, specifically related to a patient's visit "
                "with a clinician.",
                "",
                "These audio files contain recordings of a single visit.",
                "There is no overlap between the segments, so they should be regarded as a continuous flow "
                "and analyzed at once.",
                previous_transcript,
                "Your task is to:",
                "1. label each voice if multiple voices are present.",
                "2. transcribe each speaker's words with maximum accuracy.",
                "",
                "Present your findings in a JSON format within a Markdown code block:",
                "```json",
                json.dumps(
                    [
                        {
                            "voice": "voice_1/voice_2/.../voice_N",
                            "text": "the verbatim transcription of what the speaker said, or [silence] for silences",
                        },
                    ],
                    indent=1,
                ),
                "```",
                "",
                "Then, review the discussion from the top and distinguish the role of the voices "
                "(patient, clinician, nurse, parents...) in the conversation, if there is only one voice, "
                "or just only silence, assume this is the clinician",
                "",
                "Present your findings in a JSON format within a Markdown code block:",
                "```json",
                json.dumps(
                    [{"speaker": "Patient/Clinician/Nurse/...", "voice": "voice_1/voice_2/.../voice_N"}],
                    indent=1,
                ),
                "```",
                "",
            ],
        )

        response = detector.chat(JsonSchema.get(["voice_split", "voice_identification"]))
        if response.has_error:
            return response
        if len(response.content) < 2:
            return JsonExtract(has_error=True, error="partial response", content=response.content)

        discussion = response.content[0]
        speakers = {speaker["voice"]: speaker["speaker"] for speaker in response.content[1]}
        return JsonExtract(
            has_error=False,
            error="",
            content=[{"speaker": speakers[text["voice"]], "text": text["text"]} for text in discussion],
        )

    def detect_instructions(self, discussion: list[Line], known_instructions: list[Instruction]) -> list:
        common_instructions = self.common_instructions()
        if len(known_instructions) < self.settings.hierarchical_detection_threshold:
            return self.detect_instructions_flat(discussion, known_instructions, common_instructions, "allAtOnce")
        else:
            return self.detect_instructions_per_section(discussion, known_instructions, common_instructions)

    def detect_sections(self, discussion: list[Line], common_instructions: list[Base]) -> list[SectionWithTranscript]:
        schema = self.json_schema_sections(Constants.NOTE_SECTIONS)
        linked_command = defaultdict(list)
        for instruction in common_instructions:
            linked_command[instruction.note_section()].append(instruction.class_name())

        system_prompt = [
            "The conversation is in the context of a clinical encounter between patient and licensed "
            "healthcare provider.",
            "The user will submit a segment of the transcript of the visit of a patient with the healthcare provider.",
            "Your task is to identify in the transcript whether it includes information related to "
            "any of these sections:",
            "```text",
            f"* {Constants.NOTE_SECTION_ASSESSMENT}: any evaluations, diagnoses, or impressions made by "
            "the provider about the patient's condition - "
            f"linked commands: {linked_command[Constants.NOTE_SECTION_ASSESSMENT]}.",
            f"* {Constants.NOTE_SECTION_HISTORY}: any past information about the patient's medical, "
            "family, or social history that is not part of the current reason for visit - "
            f"linked commands: {linked_command[Constants.NOTE_SECTION_HISTORY]}.",
            f"* {Constants.NOTE_SECTION_OBJECTIVE}: any measurable or observable data such as physical exam findings,"
            f" test results, or vital signs - linked commands: {linked_command[Constants.NOTE_SECTION_OBJECTIVE]}.",
            f"* {Constants.NOTE_SECTION_PLAN}: any intended future actions such as treatments, follow-ups, "
            f"prescriptions, or referrals - linked commands: {linked_command[Constants.NOTE_SECTION_PLAN]}.",
            f"* {Constants.NOTE_SECTION_PROCEDURES}: any actions that have already been performed on the patient "
            "during the encounter (e.g. immunizations, suturing) - "
            f"linked commands: {linked_command[Constants.NOTE_SECTION_PROCEDURES]}.",
            f"* {Constants.NOTE_SECTION_SUBJECTIVE}: any information describing the patient's current concerns, "
            "symptoms, or the stated reason for visit (e.g. 'follow-up visit', 'check-up', 'here for cough', "
            f"'experiencing pain' - linked commands: {linked_command[Constants.NOTE_SECTION_SUBJECTIVE]}.",
            "```",
            "",
            "Your response must be in a JSON Markdown block and validated with the schema:",
            "```json",
            json.dumps(schema),
            "```",
            "",
        ]
        user_prompt = [
            "Below is the most recent segment of the transcript of the visit of a patient with a healthcare provider.",
            "What are the sections present in the transcript?",
            "```json",
            json.dumps([speaker.to_json() for speaker in discussion], indent=1),
            "```",
            "",
        ]
        memory_log = MemoryLog.instance(self.identification, "transcript2sections", self.s3_credentials)
        chatter = Helper.chatter(self.settings, memory_log, ModelSpec.COMPLEX)
        return SectionWithTranscript.load_from(
            chatter.single_conversation(
                system_prompt,
                user_prompt,
                [schema],
                None,
            )
        )

    def detect_instructions_per_section(
        self,
        discussion: list[Line],
        known_instructions: list[Instruction],
        common_instructions: list[Base],
    ) -> list:
        result: list = []
        detected_sections = self.detect_sections(discussion, common_instructions)

        # keep the instructions which are not part of the detected sections
        section_names = [detected.section for detected in detected_sections]
        no_section_instructions_names = [
            instruction.class_name()
            for instruction in common_instructions
            if instruction.note_section() not in section_names
        ]

        no_section_known_instructions = [
            instruction
            for instruction in known_instructions
            if instruction.instruction in no_section_instructions_names
        ]
        for idx, instruction in enumerate(no_section_known_instructions):
            result.append(instruction.to_json(True) | {"index": idx})

        # detect the instruction for each section
        for detected in detected_sections:
            # select the known instructions related to the section
            section_instructions = [
                instruction for instruction in common_instructions if instruction.note_section() == detected.section
            ]
            section_instructions_names = [instruction.class_name() for instruction in section_instructions]
            section_known_instructions = [
                instruction
                for instruction in known_instructions
                if instruction.instruction in section_instructions_names
            ]
            # detect the upserted instructions
            found_instructions = self.detect_instructions_flat(
                detected.transcript,
                section_known_instructions,
                section_instructions,
                detected.section,
            )
            # prevent uuid or index collisions
            count = len(result)
            other_sections_uuids = [
                instruction["uuid"]
                for instruction in result
                if instruction["instruction"] not in section_instructions_names
            ]
            for idx, instruction in enumerate(found_instructions):
                if instruction["uuid"] in other_sections_uuids:
                    instruction["uuid"] = f"instruction-{count + idx:03d}"
                result.append(instruction | {"index": count + idx})

        return result

    def detect_instructions_flat(
        self,
        discussion: list[Line],
        known_instructions: list[Instruction],
        common_instructions: list[Base],
        section: str,
    ) -> list:
        schema = self.json_schema_instructions([item.class_name() for item in common_instructions])
        definitions = [
            {"instruction": item.class_name(), "information": item.instruction_description()}
            for item in common_instructions
        ]
        system_prompt = [
            "The conversation is in the context of a clinical encounter between patient and licensed "
            "healthcare provider.",
            "The user will submit the transcript of the visit of a patient with the healthcare provider.",
            "The user needs to extract and store the relevant information in their software using structured "
            "commands as described below.",
            "Your task is to help the user by identifying the relevant instructions and their linked information, "
            "regardless of their location in the transcript. Prioritize accuracy and completeness, as omitting"
            "significant clinical information compromises patient care.",
            "Prioritize and reward comprehensive capture of all health-related discussion. Focus on"
            "accurately documenting clinical information while naturally filtering non-medical content."
            "",
            "IMPORTANT: Carefully track attribution of all health information. Before documenting any symptom, "
            "condition, test result, or medical history, verify WHO it belongs to by examining pronouns, "
            "possessive markers, and context. Information about other people (family members, friends, "
            "coworkers, etc.) must NOT be attributed to the patient. When in doubt about attribution, "
            "review the surrounding context to confirm the subject of the health information.",
            "",
            "The instructions are limited to the following:",
            "```json",
            json.dumps(definitions),
            "```",
            "",
            "Your response must be in a JSON Markdown block and validated with the schema:",
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
            "List all possible instructions as a text, and then, in a JSON markdown block, "
            "respond with the found instructions as requested",
            "",
        ]
        if known_instructions:
            content = [instruction.to_json(True) for instruction in known_instructions]
            user_prompt.extend(
                [
                    "From among all previous segments of the transcript, the following instructions were identified:",
                    "```json",
                    json.dumps(content, indent=1),
                    "```",
                    # "You must always return the previous instructions, such that you return a cumulative
                    # collection of instructions.",
                    # "You must not omit them in your response. If there is information in the transcript
                    # that is relevant to a prior "
                    # "instruction, then you can use it to update the contents of the instruction, but you
                    # must not omit any "
                    # "prior instruction from your response.",
                    "If there is information in the transcript that is relevant to a prior instruction "
                    "deemed updatable, "
                    "then you can use it to update the contents of the instruction rather than creating a new one.",
                    "But, in all cases, you must provide each and every new, updated and unchanged instructions.",
                ],
            )
        chatter = Helper.chatter(
            self.settings,
            MemoryLog.instance(self.identification, f"transcript2instructions:{section}", self.s3_credentials),
            ModelSpec.COMPLEX,
        )
        result = chatter.single_conversation(system_prompt, user_prompt, [schema], None)

        # add back the missing instructions
        return_uuids = [instruction.uuid for instruction in Instruction.load_from_json(result)]
        for instruction in known_instructions:
            if instruction.uuid not in return_uuids:
                result.append(instruction.to_json(True))

        # limit the constraints to the changed instructions only
        instructions = [
            instruction
            for instruction in Instruction.load_from_json(result)
            if instruction.is_new or instruction.is_updated
        ]
        if result and (constraints := self.instruction_constraints(instructions)):
            chatter.set_model_prompt(["```json", json.dumps(result), "```"])
            user_prompt = ["Review your response and be sure to follow these constraints:"]
            for constraint in constraints:
                user_prompt.append(f" * {constraint}")
            user_prompt.append("")
            user_prompt.append("First, review carefully your response against the constraints.")
            user_prompt.append("Then, return the original JSON if it doesn't infringe the constraints.")
            user_prompt.append("Or provide a corrected version to follow the constraints if needed.")
            user_prompt.append("")
            result = chatter.single_conversation(system_prompt, user_prompt, [schema], None)
        return result

    def create_sdk_command_parameters(self, instruction: Instruction) -> InstructionWithParameters | None:
        result: InstructionWithParameters | None = None

        structures = [self.command_structures(instruction.instruction)]
        schemas = self.command_schema(instruction.instruction)
        if not schemas:
            schemas = JsonSchema.get(["generic_parameters"])

        system_prompt = [
            f"The conversation is in the context of a clinical encounter between "
            f"patient ({self.cache.demographic__str__(False)}) and licensed healthcare provider.",
            "During the encounter, the user has identified instructions with key information to record "
            "in its software.",
            "The user will submit an instruction and the linked information grounded in the transcript, as well "
            "as the structure of the associated command.",
            "Your task is to help the user by writing correctly detailed data for the structured command.",
            "Unless explicitly instructed otherwise by the user for a specific command, "
            "you must restrict your response to information explicitly present in the transcript "
            "or prior instructions.",
            "",
            "Your response has to be a JSON Markdown block encapsulating the filled structure.",
            "",
            f"Please, note that now is {datetime.now().isoformat()}.",
        ]
        user_prompt = [
            "Based on the text:",
            "```text",
            instruction.information,
            "```",
            "",
            "Your task is to replace the values of the JSON object with the relevant information:",
            "```json",
            json.dumps(structures, indent=1),
            "```",
            "",
            "The explanations and constraints about the fields are defined in this JSON Schema:",
            "```json",
            json.dumps(schemas[0], indent=1),
            "```",
            "",
            "Be sure your response validates the JSON Schema.",
            "",
            "Before finalizing, verify completeness by checking that patient concerns are accurately captured "
            "and any provider recommendations, follow-up plans, and instructions are complete, specific "
            "and are accurate given the conversation.",
            "",
        ]
        log_label = f"{instruction.instruction}_{instruction.uuid}_instruction2parameters"
        memory_log = MemoryLog.instance(self.identification, log_label, self.s3_credentials)
        chatter = Helper.chatter(self.settings, memory_log, ModelSpec.SIMPLER)
        response = chatter.single_conversation(system_prompt, user_prompt, schemas, instruction)
        if response:
            result = InstructionWithParameters.add_parameters(instruction, response[0])
        if result:
            messages = [
                ProgressMessage(
                    message=f"parameters identified for {instruction.instruction}",
                    section=Constants.PROGRESS_SECTION_TECHNICAL,
                )
            ]
            ProgressDisplay.send_to_user(self.identification, self.settings, messages)
        return result

    def create_sdk_command_from(self, direction: InstructionWithParameters) -> InstructionWithCommand | None:
        for class_name, instance in self._command_context.items():
            if direction.instruction == class_name:
                log_label = f"{direction.instruction}_{direction.uuid}_parameters2command"
                memory_log = MemoryLog.instance(self.identification, log_label, self.s3_credentials)
                chatter = Helper.chatter(self.settings, memory_log, ModelSpec.SIMPLER)
                result = instance.command_from_json_with_summary(direction, chatter)
                if result:
                    messages = [
                        ProgressMessage(
                            message=f"command generated for {direction.instruction}",
                            section=Constants.PROGRESS_SECTION_TECHNICAL,
                        ),
                    ]
                    if summary := result.summary:
                        section = Constants.PROGRESS_SECTION_MEDICAL_NEW
                        if result.is_updated:
                            section = Constants.PROGRESS_SECTION_MEDICAL_UPDATED
                        messages.append(ProgressMessage(message=summary, section=section))

                    ProgressDisplay.send_to_user(self.identification, self.settings, messages)
                return result
        return None

    def update_questionnaire(self, discussion: list[Line], direction: Instruction) -> InstructionWithCommand | None:
        for class_name, instance in self._command_context.items():
            if direction.instruction == class_name:
                assert isinstance(instance, BaseQuestionnaire)
                log_label = f"{direction.instruction}_{direction.uuid}_questionnaire_update"
                chatter = Helper.chatter(
                    self.settings,
                    MemoryLog.instance(self.identification, log_label, self.s3_credentials),
                    ModelSpec.COMPLEX,
                )
                if questionnaire := instance.update_from_transcript(discussion, direction, chatter):
                    command = instance.command_from_questionnaire(direction.uuid, questionnaire)
                    return InstructionWithCommand(
                        uuid=direction.uuid,
                        index=direction.index,
                        instruction=direction.instruction,
                        information=json.dumps(questionnaire.to_json()),
                        is_new=False,
                        is_updated=True,
                        previous_information=direction.previous_information,
                        parameters={},
                        command=command,
                    )
        return None

    @classmethod
    def json_schema_instructions(cls, commands: list[str]) -> dict:
        properties = {
            "uuid": {
                "type": "string",
                "description": "a unique identifier in this discussion",
            },
            "index": {
                "type": "integer",
                "description": "the 0-based appearance order of the instruction in this discussion",
            },
            "instruction": {"type": "string", "enum": commands},
            "information": {
                "type": "string",
                "description": "all relevant information extracted from the discussion explaining and/or "
                "defining the instruction",
            },
            "isNew": {"type": "boolean", "description": "the instruction is new to the discussion"},
            "isUpdated": {
                "type": "boolean",
                "description": "the instruction is an update of an instruction previously identified in the discussion",
            },
        }
        required = ["uuid", "index", "instruction", "information", "isNew", "isUpdated"]

        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {"type": "object", "properties": properties, "required": required, "additionalProperties": False},
        }

    @classmethod
    def json_schema_sections(cls, sections: list[str]) -> dict:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": sections,
                    },
                    "transcript": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "speaker": {"type": "string", "minLength": 1},
                                "text": {"type": "string", "minLength": 1},
                            },
                            "required": ["speaker", "text"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["section", "transcript"],
                "additionalProperties": False,
            },
        }
