# from __future__ import annotations
import json
from datetime import datetime, timedelta

import requests
from canvas_sdk.commands.base import _BaseCommand as BaseCommand
from canvas_sdk.effects import Effect
from canvas_sdk.effects.task.task import AddTaskComment, UpdateTask, TaskStatus
from canvas_sdk.events import EventType
from canvas_sdk.protocols import BaseProtocol
from canvas_sdk.v1.data import TaskComment
from canvas_sdk.v1.data.command import Command
from canvas_sdk.v1.data.note import Note
from logger import log

from commander.protocols.audio_interpreter import AudioInterpreter
from commander.protocols.auditor import Auditor
from commander.protocols.structures.instruction import Instruction
from commander.protocols.structures.line import Line
from commander.protocols.structures.settings import Settings


# ATTENTION temporary structure while waiting for a better solution
class CachedDiscussion:
    CACHED: dict[str, "CachedDiscussion"] = {}

    def __init__(self, note_uuid: str) -> None:
        self.updated: datetime = datetime.now()
        self.count: int = 1
        self.note_uuid = note_uuid
        self.previous_instructions: list[Instruction] = []

    def add_one(self) -> None:
        self.updated = datetime.now()
        self.count = self.count + 1

    @classmethod
    def get_discussion(cls, note_uuid: str) -> "CachedDiscussion":
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
        if response.status_code == 200:
            return response.content
        return b""


class Commander(BaseProtocol):
    SECRET_OPENAI_KEY = "OpenAIKey"
    SECRET_SCIENCE_HOST = "ScienceHost"
    SECRET_ONTOLOGIES_HOST = "OntologiesHost"
    SECRET_PRE_SHARED_KEY = "PreSharedKey"
    SECRET_ALLOW_COMMAND_UPDATES = "AllowCommandUpdates"
    SECRET_AUDIO_HOST = "AudioHost"
    LABEL_ENCOUNTER_COPILOT = "Encounter Copilot"
    MAX_AUDIOS = 1

    RESPONDS_TO = [
        EventType.Name(EventType.TASK_COMMENT_CREATED),
    ]

    def compute(self) -> list[Effect]:
        comment = TaskComment.objects.get(id=self.target)
        log.info(f"--> comment: {comment.id} (task: {comment.task.id}, labels: {[r for r in comment.task.labels.all()]})")
        # if comment.task.title != self.LABEL_ENCOUNTER_COPILOT:
        if not comment.task.labels.filter(name=self.LABEL_ENCOUNTER_COPILOT).first():
            return []

        # # the context will have the OpenAIKey on local environment only (no database access yet)
        # if self.SECRET_OPENAI_KEY in self.context:
        #     self.secrets = {
        #         self.SECRET_OPENAI_KEY: self.context[self.SECRET_OPENAI_KEY],
        #         self.SECRET_SCIENCE_HOST: "https://science-staging.canvasmedical.com",
        #         self.SECRET_ONTOLOGIES_HOST: "https://ontologies-aptible-staging.canvasmedical.com",
        #         self.SECRET_PRE_SHARED_KEY: self.context[self.SECRET_PRE_SHARED_KEY],
        #         self.SECRET_AUDIO_HOST: "http://localhost:8000/protocol-draft",
        #         self.SECRET_ALLOW_COMMAND_UPDATES: True,
        #     }
        #     Constants.HAS_DATABASE_ACCESS = False

        information = json.loads(comment.body)
        chunk_index = information["chunk_index"]  # <--- starts with 1
        note_uuid = information["note_id"]
        note = Note.objects.get(id=note_uuid)
        provider_uuid = note.provider.id
        patient_uuid = note.patient.id

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

    def allow_command_updates(self) -> bool:
        result = self.secrets.get(self.SECRET_ALLOW_COMMAND_UPDATES)
        if isinstance(result, str) and result.lower() in ["yes", "y", "1"]:
            return True
        return False

    def compute_audio(self, patient_uuid: str, note_uuid: str, provider_uuid: str, chunk_index: int) -> tuple[bool, list[Effect]]:
        CachedDiscussion.clear_cache()
        # retrieve the last two audio chunks
        audios = self.retrieve_audios(self.secrets[self.SECRET_AUDIO_HOST], patient_uuid, note_uuid, chunk_index)
        log.info(f"--> audio chunks: {len(audios)}")
        if not audios:
            return False, []

        discussion = CachedDiscussion.get_discussion(note_uuid)
        discussion.add_one()
        # request the transcript of the audio (provider + patient...)
        settings = Settings(
            openai_key=self.secrets[self.SECRET_OPENAI_KEY],
            science_host=self.secrets[self.SECRET_SCIENCE_HOST],
            ontologies_host=self.secrets[self.SECRET_ONTOLOGIES_HOST],
            pre_shared_key=self.secrets[self.SECRET_PRE_SHARED_KEY],
            allow_update=self.allow_command_updates(),
        )
        discussion.previous_instructions, results = self.audio2commands(
            Auditor(),
            audios,
            AudioInterpreter(settings, patient_uuid, note_uuid, provider_uuid),
            discussion.previous_instructions,
        )
        # summary
        log.info(f"<===  note: {note_uuid} ===>")
        log.info(f"updates ok: {settings.allow_update}")
        log.info(f"instructions: {discussion.previous_instructions}")
        log.info("<-------->")
        for result in results:
            log.info(f"command: {result.type}")
            log.info(result.payload)
        log.info("<=== END ===>")

        return True, results

    @classmethod
    def audio2commands(
            cls,
            auditor: Auditor,
            audios: list[bytes],
            chatter: AudioInterpreter,
            previous_instructions: list[Instruction],
    ) -> tuple[list[Instruction], list[Effect]]:
        response = chatter.combine_and_speaker_detection(audios)
        if response.has_error is True:
            log.info(f"--> transcript encountered: {response.error}")
            return previous_instructions, []  # <--- let's continue even if we were not able to get a transcript

        transcript = Line.load_from_json(response.content)
        auditor.identified_transcript(audios, transcript)
        log.info(f"--> transcript back and forth: {len(transcript)}")

        # detect the instructions based on the transcript and the existing commands
        response = chatter.detect_instructions(transcript, previous_instructions)
        cumulated_instructions = Instruction.load_from_json(response)
        auditor.found_instructions(transcript, cumulated_instructions)
        log.info(f"--> instructions: {len(cumulated_instructions)}")
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
        new_instructions = [instruction for instruction in instructions if instruction.uuid not in past_uuids]
        log.info(f"--> new instructions: {len(new_instructions)}")
        sdk_parameters = [
            parameters
            for instruction in new_instructions
            if (parameters := chatter.create_sdk_command_parameters(instruction)) and parameters[1] is not None
        ]
        auditor.computed_parameters(sdk_parameters)

        log.info(f"--> new commands: {len(sdk_parameters)}")
        sdk_commands = [
            command
            for instruction, parameters in sdk_parameters
            if (command := chatter.create_sdk_command_from(instruction, parameters))
        ]
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
        mapping = chatter.schema_key2instruction()
        note = Note.objects.get(id=chatter.note_uuid)
        last_commands = {
            mapping.get(c.schema_key, ""): str(c.id)
            for c in Command.objects.filter(
                patient__id=chatter.patient_id,
                note_id=note.dbid,
                origination_source="plugin",  # <--- TODO use an Enum when provided
                state="staged",  # <--- TODO use an Enum when provided
            )
        }
        updated_instructions = [
            instruction
            for instruction in instructions
            if instruction.uuid in past_uuids.keys()
               and instruction.instruction in last_commands.keys()
               and instruction.instruction == past_uuids[instruction.uuid].instruction
               and instruction.information != past_uuids[instruction.uuid].information
        ]
        log.info(f"--> updated instructions: {len(updated_instructions)}")
        sdk_parameters = [
            parameters
            for instruction in updated_instructions
            if (parameters := chatter.create_sdk_command_parameters(instruction)) and parameters[1] is not None
        ]
        auditor.computed_parameters(sdk_parameters)

        log.info(f"--> updated commands: {len(sdk_parameters)}")
        sdk_commands: list[BaseCommand] = []
        for instruction, parameters in sdk_parameters:
            command = chatter.create_sdk_command_from(instruction, parameters)
            if command:
                command.command_uuid = last_commands[instruction.instruction]
                sdk_commands.append(command)

        auditor.computed_commands(sdk_parameters, sdk_commands)
        return [command.edit() for command in sdk_commands]
