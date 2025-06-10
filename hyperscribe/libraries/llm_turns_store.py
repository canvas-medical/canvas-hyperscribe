from __future__ import annotations

import json
from http import HTTPStatus
from re import search
from typing import Iterable, Tuple

from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.libraries.cached_discussion import CachedDiscussion
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.llm_turn import LlmTurn

DISCUSSIONS: dict[str, dict[int, dict[str, int]]] = {}


class LlmTurnsStore:

    @classmethod
    def end_session(cls, note_uuid: str) -> None:
        if note_uuid in DISCUSSIONS:
            del DISCUSSIONS[note_uuid]

    @classmethod
    def instance(cls, s3_credentials: AwsS3Credentials, identification: IdentificationParameters) -> LlmTurnsStore:
        cached = CachedDiscussion.get_discussion(identification.note_uuid)
        return LlmTurnsStore(s3_credentials, identification, cached.creation_day(), cached.cycle)

    def __init__(
            self,
            s3_credentials: AwsS3Credentials,
            identification: IdentificationParameters,
            creation_day: str,
            cycle: int,
    ) -> None:
        self.creation_day = creation_day
        self.cycle = cycle
        self.identification = identification
        self.s3_credentials = s3_credentials

    def store(
            self,
            instruction: str,
            index: int,
            llm_turns: list[LlmTurn],
    ) -> None:
        note_uuid = self.identification.note_uuid
        cycle = self.cycle
        key = instruction
        if index >= 0:
            key = self.indexed_instruction(instruction, index)

        if note_uuid not in DISCUSSIONS:
            DISCUSSIONS[note_uuid] = {}
        if self.cycle not in DISCUSSIONS[note_uuid]:
            DISCUSSIONS[note_uuid][cycle] = {}
        if key not in DISCUSSIONS[note_uuid][cycle]:
            DISCUSSIONS[note_uuid][cycle][key] = 0

        count = DISCUSSIONS[note_uuid][cycle][key]
        self.store_document(f"{key}_{count:02d}.json", [turn.to_dict() for turn in llm_turns])

        DISCUSSIONS[note_uuid][cycle][key] = count + 1

    def store_document(self, name: str, document: dict | list) -> None:
        client_s3 = AwsS3(self.s3_credentials)
        if client_s3.is_ready():
            client_s3.upload_text_to_s3(f"{self.store_path()}/{name}", json.dumps(document, indent=2))

    def stored_document(self, name: str) -> list:
        client_s3 = AwsS3(self.s3_credentials)
        if client_s3.is_ready():
            response = client_s3.access_s3_object(f"{self.store_path()}/{name}")
            if response.status_code == HTTPStatus.OK.value:
                return response.json() or []
        return []

    def stored_documents(self) -> Iterable[tuple[str, list]]:
        client_s3 = AwsS3(self.s3_credentials)
        if client_s3.is_ready():
            urls = [
                document.key
                for document in client_s3.list_s3_objects(self.store_path())
            ]
            for url in sorted(urls, key=self.s3_path_sort):
                response = client_s3.access_s3_object(url)
                if response.status_code == HTTPStatus.OK.value:
                    step = url.split("/")[-1].removesuffix(".json")
                    yield step, response.json() or []

    def store_path(self) -> str:
        return (f"hyperscribe-{self.identification.canvas_instance}/"
                f"llm_turns/"
                f"{self.creation_day}/"
                f"{self.identification.note_uuid}/"
                f"{self.cycle:02d}")

    @classmethod
    def s3_path_sort(cls, s3_path: str) -> Tuple[int, int]:
        filename = s3_path.split('/')[-1]
        first_digits = 999
        last_digits = 999
        if match := search(r'transcript2instructions_(\d+)', filename):
            first_digits = -1
            last_digits = int(match.group(1))
        elif match := search(r'_(\d+)_(\d+)', filename):
            first_digits = int(match.group(1))
            last_digits = int(match.group(2))
        return first_digits, last_digits

    @classmethod
    def decompose(cls, step: str) -> tuple[str, int]:
        return step[:-3], int(step[-2:])

    @classmethod
    def indexed_instruction(cls, instruction: str, index: int) -> str:
        return f"{instruction}_{index:02d}"
