import json
from datetime import datetime, UTC
from typing import LiteralString, get_type_hints

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.records.generated_note import GeneratedNote as Record


class GeneratedNote(Postgres):

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
        params: dict = {
            "now": datetime.now(UTC),
            "id": generated_note_id,
        }
        sql_where: list[str] = []
        sql_sets: list[str] = ['"updated"=%(now)s']
        for field, value in updates.items():
            if not hasattr(Record, field):
                continue
            cast_str = ""
            if get_type_hints(Record)[field] in [dict, list]:
                cast_str = "::jsonb"
            sql_sets.append(f'"{field}" = %({field})s')
            sql_where.append(f'"{field}"{cast_str}<>%({field})s{cast_str}')
            if isinstance(value, dict) or isinstance(value, list):
                params[field] = json.dumps(value)
            else:
                params[field] = value

        if sql_where:
            sql: LiteralString = f'UPDATE "generated_note" SET {", ".join(sql_sets)} WHERE "id" = %(id)s AND ({" OR ".join(sql_where)})'
            self._alter(sql, params, generated_note_id)

    def get_field(self, generated_note_id: int, field: str) -> dict:
        if hasattr(Record, field) and get_type_hints(Record)[field] in [dict]:
            sql: LiteralString = f'SELECT "{field}" FROM "generated_note" WHERE "id" = %(id)s'
            for record in self._select(sql, {"id": generated_note_id}):
                result: dict = record[field]
                return result
        return {}
