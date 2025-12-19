from __future__ import annotations

from datetime import datetime, UTC

from canvas_sdk.clients.llms import LlmTokens
from logger import log

from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters

ENTRIES: dict[str, dict[str, list[str]]] = {}  # store the logs sent to AWS S3
PROMPTS: dict[str, LlmTokens] = {}  # store the token consumptions


class MemoryLog:
    @classmethod
    def token_counts(cls, note_uuid: str) -> LlmTokens:
        return PROMPTS.get(note_uuid) or LlmTokens(prompt=0, generated=0)

    @classmethod
    def end_session(cls, note_uuid: str) -> str:
        if note_uuid not in ENTRIES:
            return ""

        ENTRIES[note_uuid]["TOKENS"] = [f"TOTAL Tokens: {PROMPTS[note_uuid].prompt} / {PROMPTS[note_uuid].generated}"]
        return "\n\n\n\n".join(
            [
                "\n".join(l)
                for l in sorted(
                    [e for e in ENTRIES.pop(note_uuid).values() if e],
                    key=lambda v: v[0],
                )
            ]
        )

    @classmethod
    def dev_null_instance(cls) -> MemoryLog:
        identification = IdentificationParameters(
            patient_uuid="",
            note_uuid="",
            provider_uuid="",
            canvas_instance="local",
        )
        instance = cls(identification, "local")
        return instance

    @classmethod
    def instance(
        cls,
        identification: IdentificationParameters,
        label: str,
        s3_credentials: AwsS3Credentials,
    ) -> MemoryLog:
        instance = cls(identification, label)
        instance.s3_credentials = s3_credentials
        return instance

    def __init__(self, identification: IdentificationParameters, label: str) -> None:
        self.identification = identification
        self.label = label
        self.counts = LlmTokens(prompt=0, generated=0)
        self.s3_credentials = AwsS3Credentials(aws_key="", aws_secret="", region="", bucket="")
        if self.identification.note_uuid not in ENTRIES:
            ENTRIES[self.identification.note_uuid] = {}
            PROMPTS[self.identification.note_uuid] = LlmTokens(prompt=0, generated=0)
        if label not in ENTRIES[self.identification.note_uuid]:
            ENTRIES[self.identification.note_uuid][self.label] = []
        self.current_idx = len(ENTRIES[self.identification.note_uuid][self.label])

    def log(self, message: str) -> None:
        ENTRIES[self.identification.note_uuid][self.label].append(f"{datetime.now(UTC).isoformat()}: {message}")

    def output(self, message: str) -> None:
        self.log(message)
        log.info(message)

    def logs(self, from_index: int, to_index: int) -> str:
        return "\n".join(ENTRIES[self.identification.note_uuid][self.label][from_index:to_index])

    def store_so_far(self) -> None:
        client_s3 = AwsS3(self.s3_credentials)
        if client_s3.is_ready():
            cached = CachedSdk.get_discussion(self.identification.note_uuid)
            log_path = (
                f"hyperscribe-{self.identification.canvas_instance}/"
                "partials/"
                f"{cached.creation_day()}/"
                f"{self.identification.note_uuid}/"
                f"{cached.cycle:02d}/"
                f"{self.label}.log"
            )
            self.log(f"---> tokens: {self.counts.prompt} / {self.counts.generated}")
            from_index = self.current_idx
            to_index = len(ENTRIES[self.identification.note_uuid][self.label])
            # self.current_idx = to_index # <-- ensure a full log is stored
            client_s3.upload_text_to_s3(log_path, self.logs(from_index, to_index))

    def add_consumption(self, counts: LlmTokens) -> None:
        self.counts.add(counts)
        PROMPTS[self.identification.note_uuid].add(counts)
