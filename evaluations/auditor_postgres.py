from __future__ import annotations

from evaluations.auditor_store import AuditorStore
from evaluations.datastores.postgres.generated_note import GeneratedNote as GeneratedNoteStore
from evaluations.helper_evaluation import HelperEvaluation


class AuditorPostgres(AuditorStore):

    def __init__(self, case: str, cycle: int, generated_note_id: int) -> None:
        super().__init__(case, cycle)
        self.case = case
        self.cycle = cycle
        self.store = GeneratedNoteStore(HelperEvaluation.postgres_credentials())
        self.generated_note_id = generated_note_id

    def upsert_audio(self, label: str, audio: bytes) -> None:
        ...  # TODO record the audio in the database

    def upsert_json(self, label: str, content: dict | list) -> None:
        self.store.update_fields(self.generated_note_id, {label: content})

    def get_json(self, label: str) -> dict:
        return self.store.get_field(self.generated_note_id, label)

    def finalize(self, errors: list[str]) -> None:
        self.store.update_fields(self.generated_note_id, {
            "cycle_count": self.cycle,
            "note_json": self.summarized_generated_commands(),
            "failed": bool(errors),
            "errors": errors,
        })
