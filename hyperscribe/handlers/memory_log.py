from __future__ import annotations

from datetime import datetime, UTC

from logger import log

from hyperscribe.handlers.aws_s3 import AwsS3
from hyperscribe.handlers.cached_discussion import CachedDiscussion
from hyperscribe.handlers.structures.aws_s3_credentials import AwsS3Credentials


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
    def instance(cls, note_uuid: str, label: str, aws_s3: AwsS3Credentials) -> MemoryLog:
        instance = cls(note_uuid, label)
        instance.aws_s3 = aws_s3
        return instance

    def __init__(self, note_uuid: str, label: str) -> None:
        self.note_uuid = note_uuid
        self.label = label
        self.aws_s3 = AwsS3Credentials(aws_key="", aws_secret="", region="", bucket="")
        if self.note_uuid not in self.ENTRIES:
            self.ENTRIES[self.note_uuid] = {}
        if label not in self.ENTRIES[self.note_uuid]:
            self.ENTRIES[self.note_uuid][self.label] = []

    def log(self, message: str) -> None:
        self.ENTRIES[self.note_uuid][self.label].append(f"{datetime.now(UTC).isoformat()}: {message}")

    def output(self, message: str) -> None:
        self.log(message)
        log.info(message)

    def logs(self) -> str:
        return "\n".join(self.ENTRIES[self.note_uuid][self.label])

    def store_so_far(self) -> None:
        client_s3 = AwsS3(self.aws_s3)
        if client_s3.is_ready():
            cached = CachedDiscussion.get_discussion(self.note_uuid)
            log_path = f"{cached.creation_day()}/partials/{self.note_uuid}/{cached.count - 1:02d}/{self.label}.log"
            client_s3.upload_text_to_s3(log_path, self.logs())
