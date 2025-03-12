from __future__ import annotations

import json
from datetime import datetime, timedelta
from http import HTTPStatus
from time import time
from typing import Iterable

import requests
from canvas_sdk.commands.base import _BaseCommand as BaseCommand
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
from hyperscribe.handlers.commands.history_of_present_illness import HistoryOfPresentIllness
from hyperscribe.handlers.commands.reason_for_visit import ReasonForVisit
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.implemented_commands import ImplementedCommands
from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.handlers.memory_log import MemoryLog
from hyperscribe.handlers.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.handlers.structures.coded_item import CodedItem
from hyperscribe.handlers.structures.instruction import Instruction
from hyperscribe.handlers.structures.line import Line
from hyperscribe.handlers.structures.settings import Settings


# ATTENTION temporary structure while waiting for a better solution
class CachedDiscussion:
    CACHED: dict[str, CachedDiscussion] = {}

    def __init__(self, note_uuid: str) -> None:
        self.updated: datetime = datetime.now()
        self.count: int = 1
        self.note_uuid = note_uuid
        self.previous_instructions: list[Instruction] = []

    def add_one(self) -> None:
        self.updated = datetime.now()
        self.count = self.count + 1

    @classmethod
    def get_discussion(cls, note_uuid: str) -> CachedDiscussion:
        if note_uuid not in cls.CACHED:
            cls.CACHED[note_uuid] = CachedDiscussion(note_uuid)
        return cls.CACHED[note_uuid]

    @classmethod
    def clear_cache(cls) -> None:
        oldest = datetime.now() - timedelta(minutes=30)
        keys = list(cls.CACHED.keys())
        for note_uuid in keys:
            if cls.CACHED[note_uuid].updated < oldest:
                del cls.CACHED[note_uuid]


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
        log.info(f"--> comment: {comment.id} (task: {comment.task.id}, labels: {[r for r in comment.task.labels.all()]})")
        # if comment.task.title != self.LABEL_ENCOUNTER_COPILOT:
        if not comment.task.labels.filter(name=self.LABEL_ENCOUNTER_COPILOT).first():
            return []

        information = json.loads(comment.body)
        chunk_index = information["chunk_index"]  # <--- starts with 1
        note_uuid = information["note_id"]
        note = Note.objects.get(id=note_uuid)
        provider_uuid = note.provider.id
        patient_uuid = note.patient.id

        memory_log = MemoryLog(note_uuid, self.MEMORY_LOG_LABEL)
        memory_log.output(f"Text: {self.secrets[Constants.SECRET_TEXT_VENDOR]} - Audio: {self.secrets[Constants.SECRET_AUDIO_VENDOR]}")
        had_audio, effects = self.compute_audio(patient_uuid, note_uuid, provider_uuid, chunk_index)
        if had_audio:
            log.info(f"audio was present => go to next iteration ({chunk_index + 1})")
            effects.append(AddTaskComment(
                task_id=str(comment.task.id),
                body=json.dumps({
                    "note_id": note_uuid,
                    "patient_id": patient_uuid,
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

    def compute_audio(
            self,
            patient_uuid: str,
            note_uuid: str,
            provider_uuid: str,
            chunk_index: int,
    ) -> tuple[bool, list[Effect]]:
        memory_log = MemoryLog(note_uuid, self.MEMORY_LOG_LABEL)
        CachedDiscussion.clear_cache()
        # retrieve the last two audio chunks
        audios = self.retrieve_audios(self.secrets[Constants.SECRET_AUDIO_HOST], patient_uuid, note_uuid, chunk_index)
        memory_log.output(f"--> audio chunks: {len(audios)}")
        if not audios:
            return False, []

        discussion = CachedDiscussion.get_discussion(note_uuid)
        discussion.add_one()
        # request the transcript of the audio (provider + patient...)
        settings = Settings.from_dictionary(self.secrets)
        aws_s3 = AwsS3Credentials.from_dictionary(self.secrets)

        current_commands = Command.objects.filter(
            patient__id=patient_uuid,
            note__id=note_uuid,
            state="staged",  # <--- TODO use an Enum when provided
        ).order_by("dbid")

        cache = LimitedCache(
            patient_uuid,
            self.existing_commands_to_coded_items(current_commands),
        )
        chatter = AudioInterpreter(
            settings,
            aws_s3,
            cache,
            patient_uuid,
            note_uuid,
            provider_uuid,
        )
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
        memory_log.output(f"<===  note: {note_uuid} ===>")
        memory_log.output(f"Structured RfV: {settings.structured_rfv}")
        memory_log.output(f"instructions: {discussion.previous_instructions}")
        memory_log.output("<-------->")
        for result in results:
            memory_log.output(f"command: {EffectType.Name(result.type)}")
            memory_log.output(result.payload)
        memory_log.output("<=== END ===>")

        if (client_s3 := AwsS3(aws_s3)) and client_s3.is_ready():
            remote_path = f"{datetime.now().date().isoformat()}/{patient_uuid}-{note_uuid}/{chunk_index:03}.log"
            memory_log.output(f"--> log path: {remote_path}")
            client_s3.upload_text_to_s3(remote_path, MemoryLog.end_session(note_uuid))
        return True, results

    @classmethod
    def audio2commands(
            cls,
            auditor: Auditor,
            audios: list[bytes],
            chatter: AudioInterpreter,
            previous_instructions: list[Instruction],
    ) -> tuple[list[Instruction], list[Effect]]:
        memory_log = MemoryLog(chatter.note_uuid, cls.MEMORY_LOG_LABEL)
        response = chatter.combine_and_speaker_detection(audios)
        if response.has_error is True:
            memory_log.output(f"--> transcript encountered: {response.error}")
            return previous_instructions, []  # <--- let's continue even if we were not able to get a transcript

        transcript = Line.load_from_json(response.content)
        auditor.identified_transcript(audios, transcript)
        memory_log.output(f"--> transcript back and forth: {len(transcript)}")

        # detect the instructions based on the transcript and the existing commands
        response = chatter.detect_instructions(transcript, previous_instructions)
        cumulated_instructions = Instruction.load_from_json(response)
        auditor.found_instructions(transcript, cumulated_instructions)
        memory_log.output(f"--> instructions: {len(cumulated_instructions)}")
        past_uuids = {instruction.uuid: instruction for instruction in previous_instructions}

        # identify the commands
        results: list[Effect] = []
        # -- new commands
        results.extend(cls.new_commands_from(auditor, chatter, cumulated_instructions, past_uuids))
        # -- updated commands
        results.extend(cls.update_commands_from(auditor, chatter, cumulated_instructions, past_uuids))

        return cumulated_instructions, results

    @classmethod
    def new_commands_from(
            cls,
            auditor: Auditor,
            chatter: AudioInterpreter,
            instructions: list[Instruction],
            past_uuids: dict[str, Instruction],
    ) -> list[Effect]:
        memory_log = MemoryLog(chatter.note_uuid, cls.MEMORY_LOG_LABEL)
        new_instructions = [instruction for instruction in instructions if instruction.uuid not in past_uuids]
        memory_log.output(f"--> new instructions: {len(new_instructions)}")
        start = time()
        max_workers = max(1, Constants.MAX_WORKERS)
        with ThreadPoolExecutor(max_workers=max_workers) as parameters_builder:
            sdk_parameters = [
                parameters
                for parameters in parameters_builder.map(chatter.create_sdk_command_parameters, new_instructions)
                if parameters[1] is not None
            ]
        auditor.computed_parameters(sdk_parameters)
        memory_log.output(f"--> new commands: {len(sdk_parameters)}")
        with ThreadPoolExecutor(max_workers=max_workers) as command_builder:
            sdk_commands = [
                command
                for command in command_builder.map(lambda params: chatter.create_sdk_command_from(*params), sdk_parameters)
                if command is not None
            ]
        memory_log.output(f"DURATION NEW: {int((time() - start) * 1000)}")
        auditor.computed_commands(sdk_parameters, sdk_commands)
        return [command.originate() for command in sdk_commands]

    @classmethod
    def update_commands_from(
            cls,
            auditor: Auditor,
            chatter: AudioInterpreter,
            instructions: list[Instruction],
            past_uuids: dict[str, Instruction],
    ) -> list[Effect]:
        memory_log = MemoryLog(chatter.note_uuid, cls.MEMORY_LOG_LABEL)
        changed = [
            instruction
            for instruction in instructions
            if instruction.uuid in past_uuids
               and past_uuids[instruction.uuid].information != instruction.information
        ]
        memory_log.output(f"--> updated instructions: {len(changed)}")
        start = time()
        max_workers = max(1, Constants.MAX_WORKERS)
        with ThreadPoolExecutor(max_workers=max_workers) as parameters_builder:
            sdk_parameters = [
                parameters
                for parameters in parameters_builder.map(chatter.create_sdk_command_parameters, changed)
                if parameters[1] is not None
            ]
        auditor.computed_parameters(sdk_parameters)
        memory_log.output(f"--> updated commands: {len(sdk_parameters)}")
        sdk_commands: list[BaseCommand] = []
        with ThreadPoolExecutor(max_workers=max_workers) as command_builder:
            for idx, command in enumerate(command_builder.map(lambda params: chatter.create_sdk_command_from(*params), sdk_parameters)):
                if command is not None:
                    command.command_uuid = changed[idx].uuid
                    sdk_commands.append(command)

        memory_log.output(f"DURATION UPDATE: {int((time() - start) * 1000)}")

        auditor.computed_commands(sdk_parameters, sdk_commands)
        return [command.edit() for command in sdk_commands]

    @classmethod
    def existing_commands_to_instructions(cls, current_commands: Iterable[Command], instructions: list[Instruction]) -> list[Instruction]:
        result: dict[str, Instruction] = {}
        consumed_indexes: list[int] = []
        mapping = ImplementedCommands.schema_key2instruction()
        for command in current_commands:
            instruction_type = mapping[command.schema_key]
            instruction_uuid = str(command.id)
            information = ""
            if command.schema_key == HistoryOfPresentIllness.schema_key():
                information = command.data.get("narrative", "")
            elif command.schema_key == ReasonForVisit.schema_key():
                information = command.data.get("comment", "")

            for idx, instruction in enumerate(instructions):
                if idx not in consumed_indexes and instruction_type == instruction.instruction:
                    consumed_indexes.append(idx)
                    information = instruction.information
                    break

            result[instruction_uuid] = Instruction(
                uuid=instruction_uuid,
                instruction=instruction_type,
                information=information,
                is_new=False,
                is_updated=False,
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
