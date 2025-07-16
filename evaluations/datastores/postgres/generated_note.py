import json
from datetime import datetime, UTC
from typing import LiteralString, get_type_hints

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.records.generated_note import GeneratedNote as Record


class GeneratedNote(Postgres):
    def last_run_for(self, case_name: str) -> tuple[int, int]:
        sql: LiteralString = """
                             SELECT c."id" AS "case_id", MAX(gn."id") AS "generated_note_id"
                             FROM "case" c
                                      JOIN generated_note gn ON c.id = gn.case_id
                             WHERE c."name" = %(name)s
                             GROUP BY c."id" """
        for record in self._select(sql, {"name": case_name}):
            return int(record["case_id"]), int(record["generated_note_id"])
        return 0, 0

    def insert(self, case: Record) -> Record:
        params = {
            "now": datetime.now(UTC),
            "case_id": case.case_id,
            "cycle_duration": case.cycle_duration,
            "cycle_count": case.cycle_count,
            "cycle_transcript_overlap": case.cycle_transcript_overlap,
            "text_llm_vendor": case.text_llm_vendor,
            "text_llm_name": case.text_llm_name,
            "note_json": json.dumps(case.note_json),
            "hyperscribe_version": case.hyperscribe_version,
            "staged_questionnaires": json.dumps(case.staged_questionnaires),
            "transcript2instructions": json.dumps(case.transcript2instructions),
            "instruction2parameters": json.dumps(case.instruction2parameters),
            "parameters2command": json.dumps(case.parameters2command),
            "failed": case.failed,
            "errors": json.dumps(case.errors),
        }
        sql = """
              INSERT INTO "generated_note" ("created", "updated", "case_id", "cycle_duration", "cycle_count", "cycle_transcript_overlap",
                                            "text_llm_vendor", "text_llm_name", "note_json", "hyperscribe_version",
                                            "staged_questionnaires", "transcript2instructions", "instruction2parameters", "parameters2command",
                                            "failed", "errors")
              VALUES (%(now)s, %(now)s, %(case_id)s, %(cycle_duration)s, %(cycle_count)s, %(cycle_transcript_overlap)s,
                      %(text_llm_vendor)s, %(text_llm_name)s, %(note_json)s, %(hyperscribe_version)s,
                      %(staged_questionnaires)s, %(transcript2instructions)s, %(instruction2parameters)s, %(parameters2command)s,
                      %(failed)s, %(errors)s) RETURNING id"""
        return Record(
            id=self._alter(sql, params, None),
            case_id=case.case_id,
            cycle_duration=case.cycle_duration,
            cycle_count=case.cycle_count,
            cycle_transcript_overlap=case.cycle_transcript_overlap,
            text_llm_vendor=case.text_llm_vendor,
            text_llm_name=case.text_llm_name,
            note_json=case.note_json,
            hyperscribe_version=case.hyperscribe_version,
            staged_questionnaires=case.staged_questionnaires,
            transcript2instructions=case.transcript2instructions,
            instruction2parameters=case.instruction2parameters,
            parameters2command=case.parameters2command,
            failed=case.failed,
            errors=case.errors,
        )

    def update_fields(self, generated_note_id: int, updates: dict) -> None:
        self._update_fields("generated_note", Record, generated_note_id, updates)

    def get_field(self, generated_note_id: int, field: str) -> dict:
        if hasattr(Record, field) and get_type_hints(Record)[field] in [dict]:
            sql: LiteralString = f'SELECT "{field}" FROM "generated_note" WHERE "id" = %(id)s'
            for record in self._select(sql, {"id": generated_note_id}):
                result: dict = record[field]
                return result
        return {}

    def runs_count_for(self, case_id: int) -> int:
        sql: LiteralString = """
                             SELECT COUNT("id") AS "count"
                             FROM "generated_note"
                             WHERE "case_id" = %(case_id)s """
        for record in self._select(sql, {"case_id": case_id}):
            return int(record["count"])
        return 0

    def delete_for(self, case_id: int) -> None:
        sql: LiteralString = """
                             DELETE
                             FROM "generated_note"
                             WHERE "case_id" = %(case_id)s RETURNING "id" """
        self._alter(sql, {"case_id": case_id}, None)
