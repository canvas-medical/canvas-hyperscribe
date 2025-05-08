from __future__ import annotations

import json
from datetime import datetime, UTC

from logger import log

from hyperscribe.handlers.aws_s3 import AwsS3
from hyperscribe.handlers.cached_discussion import CachedDiscussion
from hyperscribe.handlers.constants import Constants
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters


class MemoryLog:
    ENTRIES: dict[str, dict[str, list[str]]] = {}  # store the logs sent to AWS S3
    PROGRESS: dict[str, list[dict]] = {}  # store the messages sent to the UI

    @classmethod
    def begin_session(cls, note_uuid: str) -> None:
        if note_uuid not in cls.ENTRIES:
            cls.ENTRIES[note_uuid] = {}

    @classmethod
    def end_session(cls, note_uuid: str) -> str:
        if note_uuid not in cls.ENTRIES:
            return ""
        return "\n".join([
            "\n".join(l)
            for l in sorted(
                [e for e in cls.ENTRIES.pop(note_uuid).values() if e],
                key=lambda v: v[0],
            )
        ])

    @classmethod
    def instance(cls, identification: IdentificationParameters, label: str, s3_credentials: AwsS3Credentials) -> MemoryLog:
        instance = cls(identification, label)
        instance.s3_credentials = s3_credentials
        return instance

    def __init__(self, identification: IdentificationParameters, label: str) -> None:
        self.identification = identification
        self.label = label
        self.s3_credentials = AwsS3Credentials(aws_key="", aws_secret="", region="", bucket="")
        if self.identification.note_uuid not in self.ENTRIES:
            self.ENTRIES[self.identification.note_uuid] = {}
        if label not in self.ENTRIES[self.identification.note_uuid]:
            self.ENTRIES[self.identification.note_uuid][self.label] = []

        if (
                self.identification.note_uuid not in self.PROGRESS or
                [
                    message
                    for message in self.PROGRESS[self.identification.note_uuid]
                    if Constants.INFORMANT_END_OF_MESSAGES == message["message"]
                ]
        ):
            self.PROGRESS[self.identification.note_uuid] = []

    def log(self, message: str) -> None:
        self.ENTRIES[self.identification.note_uuid][self.label].append(f"{datetime.now(UTC).isoformat()}: {message}")

    def output(self, message: str) -> None:
        self.log(message)
        log.info(message)

    def send_to_user(self, message: str):
        now = datetime.now(UTC).isoformat()
        self.PROGRESS[self.identification.note_uuid].insert(0, {
            "time": now,
            "message": message,
        })
        s3_credentials = AwsS3Credentials(
            aws_key=self.s3_credentials.aws_key,
            aws_secret=self.s3_credentials.aws_secret,
            region=self.s3_credentials.region,
            bucket=Constants.INFORMANT_AWS_BUCKET,
        )
        client_s3 = AwsS3(s3_credentials)
        if client_s3.is_ready():
            log_path = (f"{self.identification.canvas_instance}/"
                        f"progresses/"
                        f"{self.identification.patient_uuid}.log")
            client_s3.upload_text_to_s3(log_path, json.dumps({
                "time": now,
                "messages": self.PROGRESS[self.identification.note_uuid],
            }))

    # def send_to_user(self, message: str) -> None:
    #     from requests import post as requests_post
    #     requests_post(
    #         f"http://home-app-web:8000/plugin-io/api/hyperscribe_informant/progress?patient_id={self.identification.patient_uuid}",
    #         headers={"Content-Type": "application/json"},
    #         params={},
    #         json={"time": datetime.now(UTC).isoformat(), "text": message},
    #         # verify=True,
    #         timeout=None,
    #     )

    def logs(self) -> str:
        return "\n".join(self.ENTRIES[self.identification.note_uuid][self.label])

    def store_so_far(self) -> None:
        client_s3 = AwsS3(self.s3_credentials)
        if client_s3.is_ready():
            cached = CachedDiscussion.get_discussion(self.identification.note_uuid)
            log_path = (f"{self.identification.canvas_instance}/"
                        "partials/"
                        f"{cached.creation_day()}/"
                        f"{self.identification.note_uuid}/"
                        f"{cached.count - 1:02d}/"
                        f"{self.label}.log")
            client_s3.upload_text_to_s3(log_path, self.logs())
