from __future__ import annotations

import json
from http import HTTPStatus
from time import time
from typing import Iterable

import requests
from canvas_sdk.effects import Effect, EffectType
from canvas_sdk.effects.task.task import AddTaskComment, UpdateTask, TaskStatus
from canvas_sdk.events import EventType
from canvas_sdk.protocols import BaseProtocol
from canvas_sdk.utils.http import ThreadPoolExecutor
from canvas_sdk.v1.data import TaskComment
from canvas_sdk.v1.data.command import Command
from canvas_sdk.v1.data.note import Note
from logger import log

from hyperscribe.handlers.audio_interpreter import AudioInterpreter
from hyperscribe.handlers.auditor import Auditor
from hyperscribe.handlers.aws_s3 import AwsS3
from hyperscribe.handlers.cached_discussion import CachedDiscussion
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.implemented_commands import ImplementedCommands
from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.handlers.memory_log import MemoryLog
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.line import Line
from hyperscribe.structures.settings import Settings


class Audio:
    @classmethod
    def get_audio(cls, chunk_audio_url: str) -> bytes:
        log.info(f" ---> audio url: {chunk_audio_url}")
        response = requests.get(chunk_audio_url, timeout=300)
        log.info(f"           code: {response.status_code}")
        log.info(f"        content: {len(response.content)}")
        # Check if the request was successful
        if response.status_code == HTTPStatus.OK.value:
            return response.content
        return b""


class Commander(BaseProtocol):
    LABEL_ENCOUNTER_COPILOT = "Encounter Copilot"
    MAX_AUDIOS = 1
    MEMORY_LOG_LABEL = "main"

    RESPONDS_TO = [
        EventType.Name(EventType.TASK_COMMENT_CREATED),
    ]

    def compute(self) -> list[Effect]:
        comment = TaskComment.objects.get(id=self.target)
        log.info(f"--> comment: {comment.id} (task: {comment.task.id}, labels: {'/'.join([r.name for r in comment.task.labels.all()])})")
        # if comment.task.title != self.LABEL_ENCOUNTER_COPILOT:
        if not comment.task.labels.filter(name=self.LABEL_ENCOUNTER_COPILOT).first():
            return []

        information = json.loads(comment.body)
        chunk_index = information["chunk_index"]  # <--- starts with 1
        note_uuid = information["note_id"]
        note = Note.objects.get(id=note_uuid)
        identification = IdentificationParameters(
            patient_uuid=note.patient.id,
            note_uuid=note_uuid,
            provider_uuid=note.provider.id,
            canvas_instance=self.environment[Constants.CUSTOMER_IDENTIFIER],
        )
        memory_log = MemoryLog(identification, self.MEMORY_LOG_LABEL)
        memory_log.output(f"Text: {self.secrets[Constants.SECRET_TEXT_VENDOR]} - Audio: {self.secrets[Constants.SECRET_AUDIO_VENDOR]}")
        had_audio, effects = self.compute_audio(identification, chunk_index)
        if had_audio:
            log.info(f"audio was present => go to next iteration ({chunk_index + 1})")
            effects.append(AddTaskComment(
                task_id=str(comment.task.id),
                body=json.dumps({
                    "note_id": note_uuid,
                    "patient_id": identification.patient_uuid,
                    "chunk_index": chunk_index + 1,
                })
            ).apply())
        else:
            log.info("audio was NOT present => stop the task")
            effects.append(UpdateTask(
                id=str(comment.task.id),
                status=TaskStatus.COMPLETED,
            ).apply())
        MemoryLog.end_session(note_uuid)
        return effects

    @classmethod
    def retrieve_audios(cls, host_audio: str, patient_uuid: str, note_uuid: str, chunk_index: int) -> list[bytes]:
        audio_url = f"{host_audio}/audio/{patient_uuid}/{note_uuid}"

        initial = Audio.get_audio(f"{audio_url}/{chunk_index}")
        if not initial:
            return []
        # retrieve the previous segments only if the last one is provided
        result = [
            audio
            for chunk in range(max(1, chunk_index - cls.MAX_AUDIOS), chunk_index)
            if (audio := Audio.get_audio(f"{audio_url}/{chunk}")) and len(audio) > 0
        ]
        result.append(initial)
        return result

    def compute_audio(self, identification: IdentificationParameters, chunk_index: int) -> tuple[bool, list[Effect]]:
        memory_log = MemoryLog(identification, self.MEMORY_LOG_LABEL)
        CachedDiscussion.clear_cache()
        # retrieve the last two audio chunks
        audios = self.retrieve_audios(
            self.secrets[Constants.SECRET_AUDIO_HOST],
            identification.patient_uuid,
            identification.note_uuid,
            chunk_index,
        )
        memory_log.output(f"--> audio chunks: {len(audios)}")
        if not audios:
            return False, []

        discussion = CachedDiscussion.get_discussion(identification.note_uuid)
        discussion.add_one()
        # request the transcript of the audio (provider + patient...)
        settings = Settings.from_dictionary(self.secrets)
        aws_s3 = AwsS3Credentials.from_dictionary(self.secrets)

        current_commands = Command.objects.filter(
            patient__id=identification.patient_uuid,
            note__id=identification.note_uuid,
            state="staged",  # <--- TODO use an Enum when provided
        ).order_by("dbid")

        cache = LimitedCache(
            identification.patient_uuid,
            self.existing_commands_to_coded_items(current_commands),
        )
        chatter = AudioInterpreter(settings, aws_s3, cache, identification)
        previous_instructions = self.existing_commands_to_instructions(
            current_commands,
            discussion.previous_instructions,
        )
        discussion.previous_instructions, results = self.audio2commands(
            Auditor(),
            audios,
            chatter,
            previous_instructions,
        )
        # summary
        memory_log.output(f"<===  note: {identification.note_uuid} ===>")
        memory_log.output(f"Structured RfV: {settings.structured_rfv}")
        memory_log.output("instructions:")
        for instruction in discussion.previous_instructions:
            memory_log.output(f"- {instruction.limited_str()}")
        memory_log.output("<-------->")
        for result in results:
            memory_log.output(f"command: {EffectType.Name(result.type)}")
            memory_log.output(result.payload)
        memory_log.output("<=== END ===>")

        if (client_s3 := AwsS3(aws_s3)) and client_s3.is_ready():
            remote_path = (f"{identification.canvas_instance}/"
                           f"{discussion.creation_day()}/"
                           f"{identification.patient_uuid}-{identification.note_uuid}/"
                           f"{discussion.count - 1:02}.log")
            memory_log.output(f"--> log path: {remote_path}")
            client_s3.upload_text_to_s3(remote_path, MemoryLog.end_session(identification.note_uuid))
        return True, results

    @classmethod
    def audio2commands(
            cls,
            auditor: Auditor,
            audios: list[bytes],
            chatter: AudioInterpreter,
            previous_instructions: list[Instruction],
    ) -> tuple[list[Instruction], list[Effect]]:
        memory_log = MemoryLog(chatter.identification, cls.MEMORY_LOG_LABEL)
        response = chatter.combine_and_speaker_detection(audios)
        if response.has_error is True:
            memory_log.output(f"--> transcript encountered: {response.error}")
            return previous_instructions, []  # <--- let's continue even if we were not able to get a transcript

        transcript = Line.load_from_json(response.content)
        auditor.identified_transcript(audios, transcript)
        memory_log.output(f"--> transcript back and forth: {len(transcript)}")

        return cls.transcript2commands(auditor, transcript, chatter, previous_instructions)

    @classmethod
    def transcript2commands(
            cls,
            auditor: Auditor,
            transcript: list[Line],
            chatter: AudioInterpreter,
            instructions: list[Instruction],
    ) -> tuple[list[Instruction], list[Effect]]:
        questionnaire_classes = ImplementedCommands.questionnaire_command_name_list()
        common_instructions = [i for i in instructions if i.instruction not in questionnaire_classes]
        questionnaire_instructions = [i for i in instructions if i.instruction in questionnaire_classes]

        with (ThreadPoolExecutor(max_workers=2) as builder):
            # -- common instructions
            future_common = builder.submit(
                cls.transcript2commands_common,
                auditor,
                transcript,
                chatter,
                common_instructions,
            )
            # -- questionnaires
            future_questionnaire = builder.submit(
                cls.transcript2commands_questionnaires,
                auditor,
                transcript,
                chatter,
                questionnaire_instructions,
            )
            common_commands = future_common.result()
            questionnaire_commands = future_questionnaire.result()

        common_commands[0].extend(questionnaire_commands[0])
        common_commands[1].extend(questionnaire_commands[1])
        return common_commands

    @classmethod
    def transcript2commands_common(
            cls,
            auditor: Auditor,
            transcript: list[Line],
            chatter: AudioInterpreter,
            instructions: list[Instruction],
    ) -> tuple[list[Instruction], list[Effect]]:
        memory_log = MemoryLog(chatter.identification, cls.MEMORY_LOG_LABEL)

        # detect the instructions based on the transcript and the existing commands
        response = chatter.detect_instructions(transcript, instructions)
        updated_instructions = Instruction.load_from_json(response)
        auditor.found_instructions(transcript, instructions, updated_instructions)
        memory_log.output(f"--> instructions: {len(updated_instructions)}")
        past_uuids = {instruction.uuid: instruction for instruction in instructions}

        # identify the commands
        results: list[Effect] = []
        # -- new commands
        results.extend(cls.new_commands_from(auditor, chatter, updated_instructions, past_uuids))
        # -- updated commands
        results.extend(cls.update_commands_from(auditor, chatter, updated_instructions, past_uuids))
        # reset the audit fields
        for instruction in updated_instructions:
            instruction.audits.clear()
        return updated_instructions, results

    @classmethod
    def transcript2commands_questionnaires(
            cls,
            auditor: Auditor,
            transcript: list[Line],
            chatter: AudioInterpreter,
            instructions: list[Instruction],
    ) -> tuple[list[Instruction], list[Effect]]:
        if not instructions:
            return [], []

        memory_log = MemoryLog(chatter.identification, cls.MEMORY_LOG_LABEL)
        start = time()

        max_workers = max(1, Constants.MAX_WORKERS)
        with ThreadPoolExecutor(max_workers=max_workers) as builder:
            instructions_with_command = [
                instruction
                for instruction in builder.map(
                    chatter.update_questionnaire,
                    [transcript] * len(instructions),
                    instructions,
                )
                if instruction is not None
            ]

        updated_instructions = [
            Instruction(
                uuid=result.uuid,
                instruction=result.instruction,
                information=result.information,
                is_new=result.is_new,
                is_updated=result.is_updated,
                audits=result.audits,
            )
            for result in instructions_with_command
        ]

        memory_log.output(f"DURATION QUESTIONNAIRES: {int((time() - start) * 1000)}")
        auditor.computed_questionnaires(transcript, instructions, instructions_with_command)

        cls.store_audits(chatter.aws_s3, chatter.identification, "audit_update_questionnaires", updated_instructions)

        if chatter.identification.note_uuid == Constants.FAUX_NOTE_UUID:
            # this is the case when running an evaluation against a recorded 'limited cache',
            # i.e. the patient and/or her data don't exist, something that may be checked
            # when editing the commands
            return updated_instructions, []

        effects = [result.command.edit() for result in instructions_with_command]
        return updated_instructions, effects

    @classmethod
    def new_commands_from(
            cls,
            auditor: Auditor,
            chatter: AudioInterpreter,
            instructions: list[Instruction],
            past_uuids: dict[str, Instruction],
    ) -> list[Effect]:
        memory_log = MemoryLog(chatter.identification, cls.MEMORY_LOG_LABEL)
        new_instructions = [instruction for instruction in instructions if instruction.uuid not in past_uuids]
        memory_log.output(f"--> new instructions: {len(new_instructions)}")
        start = time()
        max_workers = max(1, Constants.MAX_WORKERS)
        with ThreadPoolExecutor(max_workers=max_workers) as builder:
            instructions_with_parameter = [
                instruction
                for instruction in builder.map(chatter.create_sdk_command_parameters, new_instructions)
                if instruction is not None
            ]
        auditor.computed_parameters(instructions_with_parameter)
        memory_log.output(f"--> new commands: {len(instructions_with_parameter)}")
        with ThreadPoolExecutor(max_workers=max_workers) as builder:
            instructions_with_command = [
                instruction
                for instruction in builder.map(chatter.create_sdk_command_from, instructions_with_parameter)
                if instruction is not None
            ]

        memory_log.output(f"DURATION NEW: {int((time() - start) * 1000)}")
        auditor.computed_commands(instructions_with_command)

        cls.store_audits(chatter.aws_s3, chatter.identification, "audit_new_commands", instructions_with_command)

        if chatter.identification.note_uuid == Constants.FAUX_NOTE_UUID:
            # this is the case when running an evaluation against a recorded 'limited cache',
            # i.e. the patient and/or her data don't exist, something that may be checked
            # when originating the commands
            return []
        return [command.command.originate() for command in instructions_with_command]

    @classmethod
    def update_commands_from(
            cls,
            auditor: Auditor,
            chatter: AudioInterpreter,
            instructions: list[Instruction],
            past_uuids: dict[str, Instruction],
    ) -> list[Effect]:
        memory_log = MemoryLog(chatter.identification, cls.MEMORY_LOG_LABEL)
        changed_instructions = [
            instruction
            for instruction in instructions
            if instruction.uuid in past_uuids
               and past_uuids[instruction.uuid].information != instruction.information
        ]
        memory_log.output(f"--> updated instructions: {len(changed_instructions)}")
        start = time()
        max_workers = max(1, Constants.MAX_WORKERS)
        with ThreadPoolExecutor(max_workers=max_workers) as builder:
            instructions_with_parameter = [
                instruction
                for instruction in builder.map(chatter.create_sdk_command_parameters, changed_instructions)
                if instruction is not None
            ]
        auditor.computed_parameters(instructions_with_parameter)
        memory_log.output(f"--> updated commands: {len(instructions_with_parameter)}")
        instructions_with_command: list[InstructionWithCommand] = []
        with ThreadPoolExecutor(max_workers=max_workers) as builder:
            for instruction in builder.map(chatter.create_sdk_command_from, instructions_with_parameter):
                if instruction is not None:
                    instruction.command.command_uuid = instruction.uuid
                    instructions_with_command.append(instruction)

        memory_log.output(f"DURATION UPDATE: {int((time() - start) * 1000)}")
        auditor.computed_commands(instructions_with_command)

        cls.store_audits(chatter.aws_s3, chatter.identification, "audit_updated_commands", instructions_with_command)

        if chatter.identification.note_uuid == Constants.FAUX_NOTE_UUID:
            # this is the case when running an evaluation against a recorded 'limited cache',
            # i.e. the patient and/or her data don't exist, something that may be checked
            # when editing the commands
            return []
        return [command.command.edit() for command in instructions_with_command]

    @classmethod
    def existing_commands_to_instructions(cls, current_commands: Iterable[Command], instructions: list[Instruction]) -> list[Instruction]:
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

        for command in current_commands:
            instruction_type = mapping[command.schema_key]
            instruction_uuid = str(command.id)
            information = ""

            for initialized in pre_initialized:
                if instruction_type == initialized.class_name():
                    information = initialized.staged_command_extract(command.data).label

            for idx, instruction in enumerate(instructions):
                if idx in consumed_indexes:
                    continue
                if instruction_type == instruction.instruction:
                    consumed_indexes.append(idx)
                    information = instruction.information
                    break

            result[instruction_uuid] = Instruction(
                uuid=instruction_uuid,
                instruction=instruction_type,
                information=information,
                is_new=False,
                is_updated=False,
                audits=[],
            )
        return list(result.values())

    @classmethod
    def existing_commands_to_coded_items(cls, current_commands: Iterable[Command]) -> dict[str, list[CodedItem]]:
        result: dict[str, list[CodedItem]] = {}
        for command in current_commands:
            for command_class in ImplementedCommands.command_list():
                if command_class.schema_key() == command.schema_key:
                    if coded_item := command_class.staged_command_extract(command.data):
                        key = command.schema_key
                        if key not in result:
                            result[key] = []
                        result[key].append(coded_item)
                    break
        return result

    @classmethod
    def store_audits(cls, aws_s3: AwsS3Credentials, identification: IdentificationParameters, label: str, instructions: list[Instruction]) -> None:
        client_s3 = AwsS3(aws_s3)
        if client_s3.is_ready():
            cached = CachedDiscussion.get_discussion(identification.note_uuid)
            log_path = (f"{identification.canvas_instance}/"
                        f"{cached.creation_day()}/"
                        f"partials/"
                        f"{identification.note_uuid}/"
                        f"{cached.count - 1:02d}/"
                        f"{label}.log")
            content = []
            for instruction in instructions:
                content.append(f"--- {instruction.instruction} ({instruction.uuid}) ---")
                content.append("\n".join(instruction.audits))
            content.append("-- EOF ---")
            client_s3.upload_text_to_s3(log_path, "\n".join(content))
