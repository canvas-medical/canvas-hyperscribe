from datetime import datetime, UTC
from typing import LiteralString

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.records.experiment_result import ExperimentResult as Record


class ExperimentResult(Postgres):
    def insert(self, experiment_result: Record) -> Record:
        params = {
            "now": datetime.now(UTC),
            "experiment_id": experiment_result.experiment_id,
            "experiment_name": experiment_result.experiment_name,
            "hyperscribe_version": experiment_result.hyperscribe_version,
            "hyperscribe_tags": self.constant_dumps(experiment_result.hyperscribe_tags),
            "case_id": experiment_result.case_id,
            "case_name": experiment_result.case_name,
            "text_llm_vendor": experiment_result.text_llm_vendor,
            "text_llm_name": experiment_result.text_llm_name,
            "cycle_time": experiment_result.cycle_time,
            "cycle_transcript_overlap": experiment_result.cycle_transcript_overlap,
            "failed": experiment_result.failed,
            "errors": self.constant_dumps(experiment_result.errors),
            "generated_note_id": experiment_result.generated_note_id,
            "note_json": self.constant_dumps(experiment_result.note_json),
        }
        sql: LiteralString = """
                             INSERT INTO "experiment_result" ("created", "updated",
                                                              "experiment_id", "experiment_name",
                                                              "hyperscribe_version", "hyperscribe_tags",
                                                              "case_id", "case_name",
                                                              "text_llm_vendor", "text_llm_name",
                                                              "cycle_time", "cycle_transcript_overlap",
                                                              "failed", "errors", "generated_note_id",
                                                              "note_json")
                             VALUES (%(now)s, %(now)s,
                                     %(experiment_id)s, %(experiment_name)s,
                                     %(hyperscribe_version)s, %(hyperscribe_tags)s,
                                     %(case_id)s, %(case_name)s,
                                     %(text_llm_vendor)s, %(text_llm_name)s,
                                     %(cycle_time)s, %(cycle_transcript_overlap)s,
                                     %(failed)s, %(errors)s, %(generated_note_id)s,
                                     %(note_json)s) RETURNING id"""
        return Record(
            id=self._alter(sql, params, None),
            experiment_id=experiment_result.experiment_id,
            experiment_name=experiment_result.experiment_name,
            hyperscribe_version=experiment_result.hyperscribe_version,
            hyperscribe_tags=experiment_result.hyperscribe_tags,
            case_id=experiment_result.case_id,
            case_name=experiment_result.case_name,
            text_llm_vendor=experiment_result.text_llm_vendor,
            text_llm_name=experiment_result.text_llm_name,
            cycle_time=experiment_result.cycle_time,
            cycle_transcript_overlap=experiment_result.cycle_transcript_overlap,
            failed=experiment_result.failed,
            errors=experiment_result.errors,
            generated_note_id=experiment_result.generated_note_id,
            note_json=experiment_result.note_json,
        )

    def update_fields(self, experiment_result_id: int, updates: dict) -> None:
        self._update_fields("experiment_result", Record, experiment_result_id, updates)

    def get_generated_note_id(self, experiment_result_id: int) -> int:
        sql: LiteralString = """
                             SELECT "generated_note_id"
                             FROM "experiment_result"
                             WHERE "id" = %(id)s"""
        for record in self._select(sql, {"id": experiment_result_id}):
            return int(record["generated_note_id"])
        return 0
