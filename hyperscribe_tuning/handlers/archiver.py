# from __future__ import annotations
import json
from datetime import datetime, timezone

from canvas_sdk.effects import Effect
from canvas_sdk.events import EventType
from canvas_sdk.protocols import BaseProtocol
from canvas_sdk.v1.data import Patient
from canvas_sdk.v1.data.note import Note
from logger import log
from requests import get as requests_get

from hyperscribe_tuning.handlers.aws_s3 import AwsS3


class Audio:
    @classmethod
    def get_audio(cls, chunk_audio_url: str) -> bytes:
        log.info(f" ---> audio url: {chunk_audio_url}")
        response = requests_get(chunk_audio_url, timeout=300)
        log.info(f"           code: {response.status_code}")
        log.info(f"        content: {len(response.content)}")
        # Check if the request was successful
        if response.status_code == 200:
            return response.content
        return b""


class Archiver(BaseProtocol):
    SECRET_AWS_KEY = "AwsKey"
    SECRET_AWS_SECRET = "AwsSecret"
    SECRET_AWS_REGION = "AwsRegion"
    SECRET_AWS_BUCKET = "AwsBucket"
    SECRET_AUDIO_HOST = "AudioHost"

    RESPONDS_TO = [
        EventType.Name(EventType.PATIENT_PROFILE__SECTION_CONFIGURATION),
    ]

    def compute(self) -> list[Effect]:
        now = datetime.now(timezone.utc)
        patient = Patient.objects.get(id=self.target)
        note = Note.objects.filter(patient=patient).order_by('-dbid').first()
        patient_uuid = str(patient.id)
        note_uuid = str(note.id)
        note_db_id = note.dbid
        chunk_index = 1

        audio_url = f"{self.secrets[self.SECRET_AUDIO_HOST]}/audio/{patient_uuid}/{note_uuid}/{chunk_index}"
        audio = Audio.get_audio(audio_url)

        aws_bucket_key = f"{now.date().isoformat()}/{note_db_id:05d}.mp3"
        client_s3 = AwsS3(
            self.secrets[self.SECRET_AWS_KEY],
            self.secrets[self.SECRET_AWS_SECRET],
            self.secrets[self.SECRET_AWS_REGION],
            self.secrets[self.SECRET_AWS_BUCKET],
        )
        client_s3.upload_binary_to_s3(aws_bucket_key, audio, "audio/mpeg")

        payload = {
            "now": now.isoformat(),
            "lastUploadKey": "",
            "files": client_s3.list_s3_objects(),
        }

        log.info("===================")
        log.info(json.dumps(payload, indent=2))
        log.info("===================")
        return []
