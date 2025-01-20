# from __future__ import annotations
import json
from datetime import datetime, timedelta

import requests
from canvas_sdk.effects import Effect
from canvas_sdk.effects.task.task import AddTaskComment, UpdateTask, TaskStatus
from canvas_sdk.events import EventType
from canvas_sdk.protocols import BaseProtocol
from canvas_sdk.v1.data import TaskComment
from canvas_sdk.v1.data.note import Note
from logger import log

from commander.protocols.audio_interpreter import AudioInterpreter
from commander.protocols.constants import Constants
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
        oldest = datetime.now() - timedelta(minutes=5)
        keys = list(cls.CACHED.keys())
        for note_uuid in keys:
            if cls.CACHED[note_uuid].updated < oldest:
                del cls.CACHED[note_uuid]


class Audio:
    @classmethod
    def get_audio(cls, chunk_audio_url: str) -> bytes:
        response = requests.get(chunk_audio_url)
        # Check if the request was successful
        if response.status_code == 200:
            return response.content
        return b""


class Commander(BaseProtocol):
    SECRET_OPENAI_KEY = "OpenAIKey"
    SECRET_SCIENCE_HOST = "ScienceHost"
    SECRET_ONTOLOGIES_HOST = "OntologiesHost"
    SECRET_PRE_SHARED_KEY = "PreSharedKey"
    SECRET_AUDIO_HOST = "AudioHost"
    LABEL_ENCOUNTER_COPILOT = "Encounter Copilot"

    RESPONDS_TO = [
        EventType.Name(EventType.TASK_COMMENT_CREATED),
    ]

    def compute(self) -> list[Effect]:
        comment = TaskComment.objects.get(id=self.target)
        log.info(f"--> comment: {comment.id} (task: {comment.task.id}, labels: {[r for r in comment.task.labels.all()]})")
        if not comment.task.title == self.LABEL_ENCOUNTER_COPILOT:
            # TODO if not comment.task.labels.filter(name=self.LABEL_ENCOUNTER_COPILOT).first():
            return []

            # the context will have the OpenAIKey on local environment only (no database access yet)
        if self.SECRET_OPENAI_KEY in self.context:
            self.secrets = {
                self.SECRET_OPENAI_KEY: self.context[self.SECRET_OPENAI_KEY],
                self.SECRET_SCIENCE_HOST: "https://science-staging.canvasmedical.com",
                self.SECRET_ONTOLOGIES_HOST: "https://ontologies-aptible-staging.canvasmedical.com",
                self.SECRET_PRE_SHARED_KEY: self.context[self.SECRET_PRE_SHARED_KEY],
                self.SECRET_AUDIO_HOST: "http://localhost:8000/protocol-draft",
            }
            Constants.HAS_DATABASE_ACCESS = False

        information = json.loads(comment.body)
        chunk_index = information["chunk_index"]  # <--- starts with 1
        note_uuid = information["note_id"]
        note = Note.objects.get(id=note_uuid)
        provider_uuid = note.provider.id
        patient_uuid = note.patient.id

        had_audio, effects = self.compute_audio(patient_uuid, note_uuid, provider_uuid, chunk_index)
        if had_audio:
            effects.append(AddTaskComment(
                task_id=str(comment.task.id),
                body=json.dumps({
                    "note_id": note_uuid,
                    "patient_id": patient_uuid,
                    "chunk_index": chunk_index + 1,
                })
            ).apply())
        else:
            effects.append(UpdateTask(
                id=str(comment.task.id),
                status=TaskStatus.COMPLETED,
            ).apply())

        return effects

    def compute_audio(self, patient_uuid: str, note_uuid: str, provider_uuid: str, chunk_index: int) -> tuple[bool, list[Effect]]:
        CachedDiscussion.clear_cache()

        discussion = CachedDiscussion.get_discussion(note_uuid)
        # retrieve the last two audio chunks
        audio_url = f"{self.secrets[self.SECRET_AUDIO_HOST]}/audio/{patient_uuid}/{note_uuid}"
        audios = [
            audio
            for chunk in range(max(1, chunk_index - 1), chunk_index + 1)
            if (audio := Audio.get_audio(f"{audio_url}/{chunk}")) and len(audio) > 0
        ]
        discussion.add_one()

        # request the transcript of the audio (provider + patient...)
        cumulated_instructions: list[Instruction] = []
        sdk_commands: list[tuple[Instruction, dict]] = []
        log.info(f"--> audio chunks: {len(audios)}")
        if audios:
            settings = Settings(
                openai_key=self.secrets[self.SECRET_OPENAI_KEY],
                science_host=self.secrets[self.SECRET_SCIENCE_HOST],
                ontologies_host=self.secrets[self.SECRET_ONTOLOGIES_HOST],
                pre_shared_key=self.secrets[self.SECRET_PRE_SHARED_KEY],
            )
            chatter = AudioInterpreter(settings, patient_uuid, note_uuid, provider_uuid)
            response = chatter.combine_and_speaker_detection(audios)
            transcript: list[Line] = []
            if response.has_error is False:
                transcript = Line.load_from_json(response.content)

            # detect the instructions based on the transcript and the existing commands
            log.info(f"--> transcript back and forth: {len(transcript)}")
            if transcript:
                response = chatter.detect_instructions(transcript, discussion.previous_instructions)
                if response.has_error is False:
                    cumulated_instructions = Instruction.load_from_json(response.content)

            # identify the commands
            log.info(f"--> instructions: {len(cumulated_instructions)}")
            past_uuids = [instruction.uuid for instruction in discussion.previous_instructions]
            new_instructions = [instruction for instruction in cumulated_instructions if instruction.uuid not in past_uuids]
            log.info(f"--> new instructions: {len(new_instructions)}")
            if new_instructions:
                sdk_commands = chatter.create_sdk_commands(new_instructions)
                discussion.previous_instructions = cumulated_instructions
            log.info(f"--> new commands: {len(sdk_commands)}")

            # create the commands
            results = [
                command
                for instruction, parameters in sdk_commands
                if (command := chatter.create_command_from(instruction, parameters))
            ]

            log.info(f"<===  note: {note_uuid} ===>")
            log.info(f"instructions: {discussion.previous_instructions}")
            log.info("<-------->")
            log.info(f"sdk_commands: {sdk_commands}")
            for result in results:
                log.info(f"command: {result.constantized_key()}")
                log.info(result.values)
            log.info("<=== END ===>")

            return True, [c.originate() for c in results]
        return False, []
