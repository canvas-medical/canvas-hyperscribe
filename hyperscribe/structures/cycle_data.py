from __future__ import annotations

from http import HTTPStatus
from time import sleep
from typing import NamedTuple

from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.cycle_data_source import CycleDataSource
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.line import Line


class CycleData(NamedTuple):
    audio: bytes
    transcript: list[Line]
    source: CycleDataSource

    def is_audio(self) -> bool:
        return self.source == CycleDataSource.AUDIO

    def length(self) -> int:
        if self.is_audio():
            return len(self.audio)
        return len(self.transcript)

    @classmethod
    def s3_key_path(cls, identification: IdentificationParameters, cycle: int) -> str:
        return f"hyperscribe-{identification.canvas_instance}/cycle_data/{identification.note_uuid}/cycle_{cycle:03d}"

    @classmethod
    def content_type_text(cls) -> str:
        return "text/plain"

    @classmethod
    def from_s3(cls, aws_s3: AwsS3Credentials, identification: IdentificationParameters, cycle: int) -> CycleData:
        # ATTENTION:
        #  there could be some delay between adding the cycle to the waiting list
        #  and recording the data in S3, thus the `sleep`
        client_s3 = AwsS3(aws_s3)
        if client_s3.is_ready():
            for _ in range(Constants.CYCLE_DATA_MAX_ATTEMPTS):
                data = client_s3.access_s3_object(cls.s3_key_path(identification, cycle))
                if data.status_code == HTTPStatus.OK.value:
                    audio = b""
                    transcript = []
                    if data.headers["content-type"] == CycleData.content_type_text():
                        transcript = [Line(speaker="Clinician", text=data.text, start=0.0, end=0.0)]
                        source = CycleDataSource.TRANSCRIPT
                    else:
                        audio = data.content
                        source = CycleDataSource.AUDIO
                    return CycleData(audio=audio, transcript=transcript, source=source)
                sleep(Constants.CYCLE_DATA_PAUSE_SECONDS)

        return CycleData(audio=b"", transcript=[], source=CycleDataSource.TRANSCRIPT)
