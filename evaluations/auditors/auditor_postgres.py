from __future__ import annotations

from subprocess import check_output

from evaluations.auditors.auditor_store import AuditorStore
from evaluations.constants import Constants as EvaluationConstants
from evaluations.datastores.postgres.case import Case as CaseStore
from evaluations.datastores.postgres.generated_note import GeneratedNote as GeneratedNoteStore
from evaluations.structures.enums.case_status import CaseStatus
from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.structures.records.case import Case as CaseRecord
from evaluations.structures.records.generated_note import GeneratedNote as GeneratedNoteRecord
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.line import Line
from hyperscribe.structures.settings import Settings


class AuditorPostgres(AuditorStore):
    def __init__(
        self,
        case: str,
        cycle: int,
        settings: Settings,
        aws_s3_credentials: AwsS3Credentials,
        postgres_credentials: PostgresCredentials,
    ) -> None:
        super().__init__(case, cycle, settings, aws_s3_credentials)
        self.postgres_credentials = postgres_credentials
        self._case_id: int | None = None
        self._generated_note_id: int | None = None

    def case_id(self) -> int:
        if self._case_id is None:
            self._case_id = CaseStore(self.postgres_credentials).get_id(self.case)
        return self._case_id

    def generated_note_id(self) -> int:
        if self._generated_note_id is None:
            self._generated_note_id = (
                GeneratedNoteStore(self.postgres_credentials)
                .insert(
                    GeneratedNoteRecord(
                        case_id=self.case_id(),
                        cycle_duration=0,
                        cycle_count=0,  # <-- updated at the end
                        note_json=[],  # <-- updated at the end
                        cycle_transcript_overlap=self.settings.cycle_transcript_overlap,
                        text_llm_vendor=self.settings.llm_text.vendor,
                        text_llm_name=self.settings.llm_text_model(),
                        hyperscribe_version=self.get_plugin_commit(),
                        failed=True,  # <-- will be changed to False at the end
                    ),
                )
                .id
            )
        return self._generated_note_id

    def case_prepare(self) -> None:
        store = CaseStore(self.postgres_credentials)
        self._case_id = store.get_id(self.case)
        if self._case_id == 0:
            self._case_id = store.upsert(
                CaseRecord(name=self.case, profile=self.case, validationStatus=CaseStatus.GENERATION),
            ).id
        else:
            store.update_fields(self._case_id, {"validationStatus": CaseStatus.GENERATION})

    def case_update_limited_cache(self, limited_cache: dict) -> None:
        CaseStore(self.postgres_credentials).update_fields(self.case_id(), {"limited_chart": limited_cache})

    def case_finalize(self, errors: dict) -> None:
        GeneratedNoteStore(self.postgres_credentials).update_fields(
            self.generated_note_id(),
            {
                "cycle_count": self.cycle,
                "note_json": self.summarized_generated_commands(),
                "failed": bool(errors),
                "errors": errors,
            },
        )

    def upsert_audio(self, label: str, audio: bytes) -> None:
        # TODO record the audio in the database
        ...

    def upsert_json(self, label: str, content: dict) -> None:
        if label == EvaluationConstants.AUDIO2TRANSCRIPT:
            store = CaseStore(self.postgres_credentials)
            transcript = {
                key: [line.to_json() for line in lines] for key, lines in store.get_transcript(self.case_id()).items()
            }
            store.update_fields(self.case_id(), {"transcript": transcript | content})
        else:
            GeneratedNoteStore(self.postgres_credentials).update_fields(self.generated_note_id(), {label: content})

    def get_json(self, label: str) -> dict:
        return GeneratedNoteStore(self.postgres_credentials).get_field(self.generated_note_id(), label)

    def limited_chart(self) -> dict:
        return CaseStore(self.postgres_credentials).get_limited_chart(self.case_id())

    def transcript(self) -> list[Line]:
        return self.full_transcript().get(self.cycle_key, [])

    def full_transcript(self) -> dict[str, list[Line]]:
        return CaseStore(self.postgres_credentials).get_transcript(self.case_id())

    def note_uuid(self) -> str:
        return f"{self.case_id():010d}x{self.generated_note_id():010d}"

    @classmethod
    def get_plugin_commit(cls) -> str:
        return check_output(["git", "rev-parse", "--short", "HEAD"]).decode("ascii").strip()
