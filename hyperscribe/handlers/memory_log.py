from __future__ import annotations

from datetime import datetime, UTC

from logger import log

from hyperscribe.handlers.aws_s3 import AwsS3
from hyperscribe.handlers.cached_discussion import CachedDiscussion
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters


class MemoryLog:
    ENTRIES: dict[str, dict[str, list[str]]] = {}

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
    def instance(cls, identification: IdentificationParameters, label: str, aws_s3: AwsS3Credentials) -> MemoryLog:
        instance = cls(identification, label)
        instance.aws_s3 = aws_s3
        return instance

    def __init__(self, identification: IdentificationParameters, label: str) -> None:
        self.identification = identification
        self.label = label
        self.aws_s3 = AwsS3Credentials(aws_key="", aws_secret="", region="", bucket="")
        if self.identification.note_uuid not in self.ENTRIES:
            self.ENTRIES[self.identification.note_uuid] = {}
        if label not in self.ENTRIES[self.identification.note_uuid]:
            self.ENTRIES[self.identification.note_uuid][self.label] = []

    def log(self, message: str) -> None:
        self.ENTRIES[self.identification.note_uuid][self.label].append(f"{datetime.now(UTC).isoformat()}: {message}")

    def output(self, message: str) -> None:
        self.log(message)
        log.info(message)

    def logs(self) -> str:
        return "\n".join(self.ENTRIES[self.identification.note_uuid][self.label])

    def store_so_far(self) -> None:
        client_s3 = AwsS3(self.aws_s3)
        if client_s3.is_ready():
            cached = CachedDiscussion.get_discussion(self.identification.note_uuid)
            log_path = (f"{self.identification.canvas_instance}/"
                        f"{cached.creation_day()}/"
                        f"partials/"
                        f"{self.identification.note_uuid}/"
                        f"{cached.count - 1:02d}/"
                        f"{self.label}.log")
            client_s3.upload_text_to_s3(log_path, self.logs())
