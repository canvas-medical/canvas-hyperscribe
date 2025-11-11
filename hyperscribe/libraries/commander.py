from __future__ import annotations

import json
from time import time
from typing import Iterable

from canvas_sdk.effects import Effect, EffectType
from canvas_sdk.protocols import BaseProtocol
from canvas_sdk.utils.http import ThreadPoolExecutor
from canvas_sdk.v1.data.command import Command

from hyperscribe.handlers.progress_display import ProgressDisplay
from hyperscribe.libraries.audio_client import AudioClient
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.auditor_base import AuditorBase
from hyperscribe.libraries.auditor_live import AuditorLive
from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.line import Line
from hyperscribe.structures.progress_message import ProgressMessage
from hyperscribe.structures.settings import Settings


class Commander(BaseProtocol):
    @classmethod
    def compute_audio(
        cls,
        identification: IdentificationParameters,
        settings: Settings,
        aws_s3: AwsS3Credentials,
        audio_client: AudioClient,
        chunk_index: int,
    ) -> tuple[bool, list[Effect]]:
        audio_bytes = audio_client.get_audio_chunk(identification.patient_uuid, identification.note_uuid, chunk_index)

        memory_log = MemoryLog.instance(identification, Constants.MEMORY_LOG_LABEL, aws_s3)
        memory_log.output(f"--> audio length: {len(audio_bytes)}")
        if not audio_bytes:
            return False, []

        messages = [
            ProgressMessage(
                message=f"starting the cycle {chunk_index}...",
                section=Constants.PROGRESS_SECTION_TECHNICAL,
            )
        ]
        ProgressDisplay.send_to_user(identification, settings, messages)
        discussion = CachedSdk.get_discussion(identification.note_uuid)
        discussion.set_cycle(chunk_index)

        # request the transcript of the audio (provider + patient...)
        current_commands = Command.objects.filter(
            patient__id=identification.patient_uuid,
            note__id=identification.note_uuid,
            state="staged",  # <--- TODO use an Enum when provided
        ).order_by("dbid")

        cache = LimitedCache(
            identification.patient_uuid,
            identification.provider_uuid,
            cls.existing_commands_to_coded_items(current_commands, settings.commands_policy, True),
        )
        chatter = AudioInterpreter(settings, aws_s3, cache, identification)
        previous_instructions = cls.existing_commands_to_instructions(
            current_commands,
            discussion.previous_instructions,
        )
        auditor = AuditorLive(chunk_index, settings, aws_s3, identification)
        discussion.previous_instructions, results, discussion.previous_transcript = cls.audio2commands(
            auditor,
            audio_bytes,
            chatter,
            previous_instructions,
            discussion.previous_transcript,
        )
        discussion.save()
        # summary
        memory_log.output(f"<===  note: {identification.note_uuid} ===>")
        memory_log.output(f"Structured RfV: {settings.structured_rfv}")
        memory_log.output(f"Audit LLM Decisions: {settings.audit_llm}")
        memory_log.output("instructions:")
        for instruction in discussion.previous_instructions:
            memory_log.output(f"- {instruction.limited_str()}")
        memory_log.output("<-------->")
        for result in results:
            memory_log.output(f"command: {EffectType.Name(result.type)}")
            memory_log.output(result.payload)
        memory_log.output("<=== END ===>")

        if (client_s3 := AwsS3(aws_s3)) and client_s3.is_ready():
            remote_path = (
                f"hyperscribe-{identification.canvas_instance}/"
                "finals/"
                f"{discussion.creation_day()}/"
                f"{identification.patient_uuid}-{identification.note_uuid}/"
                f"{discussion.cycle:02}.log"
            )
            memory_log.output(f"--> log path: {remote_path}")
            client_s3.upload_text_to_s3(remote_path, MemoryLog.end_session(identification.note_uuid))
        return True, results

    @classmethod
    def audio2commands(
        cls,
        auditor: AuditorBase,
        audio_bytes: bytes,
        chatter: AudioInterpreter,
        previous_instructions: list[Instruction],
        previous_transcript: list[Line],
    ) -> tuple[list[Instruction], list[Effect], list[Line]]:
        memory_log = MemoryLog.instance(chatter.identification, Constants.MEMORY_LOG_LABEL, chatter.s3_credentials)
        response = chatter.combine_and_speaker_detection(audio_bytes, previous_transcript)
        if response.has_error is True:
            memory_log.output(f"--> transcript encountered: {response.error}")
            return previous_instructions, [], []  # <--- let's continue even if we were not able to get a transcript

        transcript = Line.load_from_json(response.content)
        auditor.identified_transcript(audio_bytes, transcript)
        memory_log.output(f"--> transcript back and forth: {len(transcript)}")
        messages = [
            ProgressMessage(
                message=json.dumps([line.to_json() for line in transcript]),
                section=Constants.PROGRESS_SECTION_TRANSCRIPT,
            )
        ]
        ProgressDisplay.send_to_user(chatter.identification, chatter.settings, messages)
        instructions, effects = cls.transcript2commands(auditor, transcript, chatter, previous_instructions)
        transcript_tail = Line.tail_of(transcript, chatter.settings.cycle_transcript_overlap)
        return instructions, effects, transcript_tail

    @classmethod
    def transcript2commands(
        cls,
        auditor: AuditorBase,
        transcript: list[Line],
        chatter: AudioInterpreter,
        instructions: list[Instruction],
    ) -> tuple[list[Instruction], list[Effect]]:
        questionnaire_classes = ImplementedCommands.questionnaire_command_name_list()
        common_instructions = [i for i in instructions if i.instruction not in questionnaire_classes]
        questionnaire_instructions = [i for i in instructions if i.instruction in questionnaire_classes]

        with ThreadPoolExecutor(max_workers=2) as builder:
            # -- common instructions
            future_common = builder.submit(
                Helper.with_cleanup(cls.transcript2commands_common),
                auditor,
                transcript,
                chatter,
                common_instructions,
            )
            # -- questionnaires
            future_questionnaire = builder.submit(
                Helper.with_cleanup(cls.transcript2commands_questionnaires),
                auditor,
                transcript,
                chatter,
                questionnaire_instructions,
            )
            common_commands = future_common.result()
            questionnaire_commands = future_questionnaire.result()

        common_commands[0].extend(questionnaire_commands[0])
        common_commands[1].extend(questionnaire_commands[1])
        return common_commands  # type: ignore

    @classmethod
    def transcript2commands_common(
        cls,
        auditor: AuditorBase,
        transcript: list[Line],
        chatter: AudioInterpreter,
        instructions: list[Instruction],
    ) -> tuple[list[Instruction], list[Effect]]:
        memory_log = MemoryLog.instance(chatter.identification, Constants.MEMORY_LOG_LABEL, chatter.s3_credentials)

        start = time()
        # detect the instructions based on the transcript and the existing commands
        response = chatter.detect_instructions(transcript, instructions)
        cumulated_instructions = Instruction.load_from_json(response)
        auditor.found_instructions(transcript, instructions, cumulated_instructions)
        memory_log.output(f"--> instructions: {len(cumulated_instructions)}")
        past_uuids = {instruction.uuid: instruction for instruction in instructions}

        computed_instructions: list[Instruction] = []
        detected_new: dict[str, int] = {}
        detected_updated: dict[str, int] = {}
        for instruction in cumulated_instructions:
            label = instruction.instruction
            instruction.is_new = False
            instruction.is_updated = False
            instruction.previous_information = instruction.information
            if instruction.uuid not in past_uuids:
                instruction.is_new = True
                instruction.previous_information = ""
                computed_instructions.append(instruction)
                if label not in detected_new:
                    detected_new[label] = 0
                detected_new[label] = detected_new[label] + 1
            elif past_uuids[instruction.uuid].information != instruction.information:
                instruction.is_updated = True
                instruction.previous_information = past_uuids[instruction.uuid].information
                computed_instructions.append(instruction)
                if label not in detected_updated:
                    detected_updated[label] = 0
                detected_updated[label] = detected_updated[label] + 1

        memory_log.output(f"--> computed instructions: {len(computed_instructions)}")

        detected = []
        if detected_new:
            detected.append(f"new: {', '.join([f'{k}: {v}' for k, v in detected_new.items()])}")
        if detected_updated:
            detected.append(f"updated: {', '.join([f'{k}: {v}' for k, v in detected_updated.items()])}")
        detected.append(f"total: {len(cumulated_instructions)}")
        messages = [
            ProgressMessage(
                message=f"instructions detection: {', '.join(detected)}",
                section=Constants.PROGRESS_SECTION_TECHNICAL,
            )
        ]
        ProgressDisplay.send_to_user(chatter.identification, chatter.settings, messages)

        max_workers = max(1, chatter.settings.max_workers)
        with ThreadPoolExecutor(max_workers=max_workers) as builder:
            instructions_with_parameter = [
                instruction
                for instruction in builder.map(
                    Helper.with_cleanup(chatter.create_sdk_command_parameters),
                    computed_instructions,
                )
                if instruction is not None
            ]
        memory_log.output(f"--> computed commands: {len(instructions_with_parameter)}")
        messages = [
            ProgressMessage(
                message=f"parameters computation done ({len(instructions_with_parameter)})",
                section=Constants.PROGRESS_SECTION_TECHNICAL,
            )
        ]
        ProgressDisplay.send_to_user(chatter.identification, chatter.settings, messages)
        auditor.computed_parameters(instructions_with_parameter)

        instructions_with_command: list[InstructionWithCommand] = []
        with ThreadPoolExecutor(max_workers=max_workers) as builder:
            for instruction_w_cmd in builder.map(
                Helper.with_cleanup(chatter.create_sdk_command_from),
                instructions_with_parameter,
            ):
                if instruction_w_cmd is not None:
                    if instruction_w_cmd.uuid in past_uuids:
                        instruction_w_cmd.command.command_uuid = instruction_w_cmd.uuid
                    instructions_with_command.append(instruction_w_cmd)

        memory_log.output(f"DURATION COMMONS: {int((time() - start) * 1000)}")
        messages = [
            ProgressMessage(
                message=f"commands generation done ({len(instructions_with_command)})",
                section=Constants.PROGRESS_SECTION_TECHNICAL,
            )
        ]
        ProgressDisplay.send_to_user(chatter.identification, chatter.settings, messages)
        auditor.computed_commands(instructions_with_command)

        if chatter.is_local_data:
            # this is the case when running an evaluation against a recorded 'limited cache',
            # i.e., the patient and/or her data don't exist, something that may be checked
            # when editing/originating the commands
            return cumulated_instructions, []
        return cumulated_instructions, [
            i.command.edit() if i.uuid in past_uuids else i.command.originate() for i in instructions_with_command
        ]

    @classmethod
    def transcript2commands_questionnaires(
        cls,
        auditor: AuditorBase,
        transcript: list[Line],
        chatter: AudioInterpreter,
        instructions: list[Instruction],
    ) -> tuple[list[Instruction], list[Effect]]:
        if not instructions:
            auditor.computed_questionnaires(transcript, [], [])
            return [], []

        memory_log = MemoryLog.instance(chatter.identification, Constants.MEMORY_LOG_LABEL, chatter.s3_credentials)
        start = time()

        max_workers = max(1, chatter.settings.max_workers)
        with ThreadPoolExecutor(max_workers=max_workers) as builder:
            instructions_with_command = [
                instruction
                for instruction in builder.map(
                    Helper.with_cleanup(chatter.update_questionnaire),
                    [transcript] * len(instructions),
                    instructions,
                )
                if instruction is not None
            ]

        updated_instructions = [
            Instruction(
                uuid=result.uuid,
                index=result.index,
                instruction=result.instruction,
                information=result.information,
                is_new=result.is_new,
                is_updated=result.is_updated,
                previous_information="",
            )
            for result in instructions_with_command
        ]

        memory_log.output(f"DURATION QUESTIONNAIRES: {int((time() - start) * 1000)}")
        messages = [
            ProgressMessage(
                message=f"questionnaires update done ({len(instructions_with_command)})",
                section=Constants.PROGRESS_SECTION_TECHNICAL,
            )
        ]
        ProgressDisplay.send_to_user(chatter.identification, chatter.settings, messages)
        auditor.computed_questionnaires(transcript, instructions, instructions_with_command)

        if chatter.is_local_data:
            # this is the case when running an evaluation against a recorded 'limited cache',
            # i.e., the patient and/or her data don't exist, something that may be checked
            # when editing the commands
            return updated_instructions, []

        effects = [result.command.edit() for result in instructions_with_command]
        return updated_instructions, effects

    @classmethod
    def new_commands_from(
        cls,
        auditor: AuditorBase,
        chatter: AudioInterpreter,
        instructions: list[Instruction],
        past_uuids: dict[str, Instruction],
    ) -> list[Effect]:
        memory_log = MemoryLog(chatter.identification, Constants.MEMORY_LOG_LABEL)
        new_instructions = [instruction for instruction in instructions if instruction.uuid not in past_uuids]
        memory_log.output(f"--> new instructions: {len(new_instructions)}")
        start = time()
        max_workers = max(1, chatter.settings.max_workers)
        with ThreadPoolExecutor(max_workers=max_workers) as builder:
            instructions_with_parameter = [
                instruction
                for instruction in builder.map(
                    Helper.with_cleanup(chatter.create_sdk_command_parameters),
                    new_instructions,
                )
                if instruction is not None
            ]
        auditor.computed_parameters(instructions_with_parameter)
        memory_log.output(f"--> new commands: {len(instructions_with_parameter)}")
        with ThreadPoolExecutor(max_workers=max_workers) as builder:
            instructions_with_command = [
                instruction
                for instruction in builder.map(
                    Helper.with_cleanup(chatter.create_sdk_command_from),
                    instructions_with_parameter,
                )
                if instruction is not None
            ]

        memory_log.output(f"DURATION NEW: {int((time() - start) * 1000)}")
        auditor.computed_commands(instructions_with_command)

        if chatter.is_local_data:
            # this is the case when running an evaluation against a recorded 'limited cache',
            # i.e., the patient and/or her data don't exist, something that may be checked
            # when originating the commands
            return []
        return [command.command.originate() for command in instructions_with_command]

    @classmethod
    def update_commands_from(
        cls,
        auditor: AuditorBase,
        chatter: AudioInterpreter,
        instructions: list[Instruction],
        past_uuids: dict[str, Instruction],
    ) -> list[Effect]:
        memory_log = MemoryLog(chatter.identification, Constants.MEMORY_LOG_LABEL)
        changed_instructions = [
            instruction
            for instruction in instructions
            if instruction.uuid in past_uuids and past_uuids[instruction.uuid].information != instruction.information
        ]
        memory_log.output(f"--> updated instructions: {len(changed_instructions)}")
        start = time()
        max_workers = max(1, chatter.settings.max_workers)
        with ThreadPoolExecutor(max_workers=max_workers) as builder:
            instructions_with_parameter = [
                instruction
                for instruction in builder.map(
                    Helper.with_cleanup(chatter.create_sdk_command_parameters),
                    changed_instructions,
                )
                if instruction is not None
            ]
        auditor.computed_parameters(instructions_with_parameter)
        memory_log.output(f"--> updated commands: {len(instructions_with_parameter)}")
        instructions_with_command: list[InstructionWithCommand] = []
        with ThreadPoolExecutor(max_workers=max_workers) as builder:
            for instruction in builder.map(
                Helper.with_cleanup(chatter.create_sdk_command_from),
                instructions_with_parameter,
            ):
                if instruction is not None:
                    instruction.command.command_uuid = instruction.uuid
                    instructions_with_command.append(instruction)

        memory_log.output(f"DURATION UPDATE: {int((time() - start) * 1000)}")
        auditor.computed_commands(instructions_with_command)

        if chatter.is_local_data:
            # this is the case when running an evaluation against a recorded 'limited cache',
            # i.e., the patient and/or her data don't exist, something that may be checked
            # when editing the commands
            return []
        return [command.command.edit() for command in instructions_with_command]

    @classmethod
    def existing_commands_to_instructions(
        cls,
        current_commands: Iterable[Command],
        instructions: list[Instruction],
    ) -> list[Instruction]:
        # convert the current commands of the note to instructions
        # then, try to match them to previously identified instructions
        result: dict[str, Instruction] = {}
        mapping = ImplementedCommands.schema_key2instruction()
        consumed_indexes: list[int] = [
            # questionnaire instructions are marked as consumed as we use the current status of the command
            # vvv - uncomment below to keep the current state of the questionnaire in the UI note
            # idx
            # for idx, instruction in enumerate(instructions)
            # if instruction.instruction in ImplementedCommands.questionnaire_command_name_list()
            # ^^^
        ]

        pre_initialized = ImplementedCommands.pre_initialized()

        for index, command in enumerate(current_commands):
            instruction_type = mapping[command.schema_key]
            instruction_uuid = str(command.id)
            information = ""

            for initialized in pre_initialized:
                if instruction_type == initialized.class_name() and (
                    code_item := initialized.staged_command_extract(command.data)
                ):
                    information = code_item.label

            for idx, instruction in enumerate(instructions):
                if idx in consumed_indexes:
                    continue
                if instruction_type == instruction.instruction:
                    consumed_indexes.append(idx)
                    information = instruction.information
                    break

            result[instruction_uuid] = Instruction(
                uuid=instruction_uuid,
                index=index,
                instruction=instruction_type,
                information=information,
                is_new=False,
                is_updated=False,
                previous_information="",
            )
        return list(result.values())

    @classmethod
    def existing_commands_to_coded_items(
        cls,
        current_commands: Iterable[Command],
        commands_policy: AccessPolicy,
        real_uuids: bool,
    ) -> dict[str, list[CodedItem]]:
        result: dict[str, list[CodedItem]] = {}
        for command in current_commands:
            for command_class in ImplementedCommands.command_list():
                if (
                    commands_policy.is_allowed(command_class.class_name())
                    and command_class.schema_key() == command.schema_key
                ):
                    if coded_item := command_class.staged_command_extract(command.data):
                        key = command.schema_key
                        if key not in result:
                            result[key] = []
                        result[key].append(
                            CodedItem(
                                uuid=str(command.id) if real_uuids else coded_item.uuid,
                                label=coded_item.label,
                                code=coded_item.code,
                            ),
                        )
                    break
        return result
