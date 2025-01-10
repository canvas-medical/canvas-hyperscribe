# from __future__ import annotations
from datetime import datetime, timedelta

import requests
from canvas_sdk.effects import Effect
from canvas_sdk.events import EventType
from canvas_sdk.protocols import BaseProtocol
from canvas_sdk.v1.data import BillingLineItem
from logger import log

from commander.protocols.audio_interpreter import AudioInterpreter
from commander.protocols.structures.instruction import Instruction
from commander.protocols.structures.line import Line


# ATTENTION temporary structure while waiting for a better solution
class CachedDiscussion:
    CACHED: dict[str, "CachedDiscussion"] = {}

    def __init__(self, note_uuid: str) -> None:
        self.updated: datetime = datetime.now()
        self.count: int = 0
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


# ATTENTION temporary way to retrieve the audios while waiting to receive them through the context
class Audio:
    @classmethod
    def get_audio(cls, chunk: int) -> bytes:
        url = f"http://localhost:8000/protocol-draft/audio/{chunk}"
        response = requests.get(url)
        # Check if the request was successful
        if response.status_code == 200:
            return response.content
        return b""


class Commander(BaseProtocol):
    SECRET_OPENAI_KEY = "OpenAIKey"
    RESPONDS_TO = [
        EventType.Name(EventType.BILLING_LINE_ITEM_CREATED),  # ATTENTION react on the right event (e.g. CONSULTATION_RECORD)
        # EventType.Name(EventType.INSTRUCTION_CREATED),
    ]

    def compute(self) -> list[Effect]:
        result: list[Effect] = []
        event = EventType.Name(self.event.type)

        log.info(f"COMMANDER PLUGIN STARTS ({event})")
        # log.info(f"target: {self.target}")
        # log.info(f"context: {self.context}")

        if event == EventType.Name(EventType.BILLING_LINE_ITEM_CREATED):
            note_uuid = self.get_note_uuid()
            patient_uuid = self.get_patient_uuid()
            result = self.compute_audio(patient_uuid, note_uuid)

        # elif event == EventType.Name(EventType.INSTRUCTION_CREATED):
        #     pass

        log.info(f"COMMANDER PLUGIN ENDS ({event})")
        return result

    def get_note_uuid(self) -> str:
        # ATTENTION the target is the billing item ==> retrieve the note id
        billing = BillingLineItem.objects.filter(id=self.target)
        note_uuid = str(billing[0].note.id)
        body = billing[0].note.body

        # retrieve all the commands of the note
        # ATTENTION this does not allow for now to actually find its content because of the lack of database access
        assert isinstance(body, list)
        commands: list[dict] = []
        for component in body:
            assert isinstance(component, dict)
            if component.get("type") == "command":
                commands.append({
                    "command": component["value"],
                    "id": component["data"]["id"],
                })
        return note_uuid

    def get_patient_uuid(self) -> str:
        # ATTENTION the target is the billing item ==> retrieve the patient id
        billing = BillingLineItem.objects.filter(id=self.target)
        return str(billing[0].patient.id)

    def compute_audio(self, patient_uuid: str, note_uuid: str) -> list[Effect]:
        CachedDiscussion.clear_cache()

        discussion = CachedDiscussion.get_discussion(note_uuid)
        # retrieve the last two audio chunks ATTENTION the context should have the audio
        audios = [
            audio
            for chunk in range(max(0, discussion.count - 1), discussion.count + 1)
            if (audio := Audio.get_audio(chunk)) and len(audio) > 0
        ]
        discussion.add_one()

        # request the transcript of the audio (provider + patient...)
        cumulated_instructions: list[Instruction] = []
        sdk_commands: list[tuple[Instruction, dict]] = []
        log.info(f"--> audio chunks: {len(audios)}")
        if audios:
            chatter = AudioInterpreter(self.secrets[self.SECRET_OPENAI_KEY], patient_uuid, note_uuid)
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
                command.originate()
                for instruction, parameters in sdk_commands
                if (command := chatter.create_command_from(instruction, parameters))
            ]

            log.info(f"<===  note: {note_uuid} ===>")
            log.info(f"instructions: {discussion.previous_instructions}")
            log.info("<-------->")
            log.info(f"sdk_commands: {sdk_commands}")
            log.info("<=== END ===>")

            return results
        return []
