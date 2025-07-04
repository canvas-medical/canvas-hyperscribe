import json
from datetime import datetime, UTC
from typing import LiteralString

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.records.case import Case as Record


class Case(Postgres):

    def get_case(self, name: str) -> Record:
        sql: LiteralString = """
                             SELECT "id",
                                    "name",
                                    "transcript",
                                    "limited_chart",
                                    "profile",
                                    "validation_status",
                                    "batch_identifier",
                                    "tags"
                             FROM "case"
                             WHERE "name" = %(name)s"""
        for record in self._select(sql, {"name": name}):
            return Record.load_record(record)
        return Record(name=name)

    def upsert(self, case: Record) -> Record:
        params = {
            "now": datetime.now(UTC),
            "name": case.name,
            "transcript": json.dumps([line.to_json() for line in case.transcript]),
            "limited_chart": json.dumps(case.limited_chart),
            "profile": case.profile,
            "validation_status": case.validation_status.value,
            "batch_identifier": case.batch_identifier,
            "tags": json.dumps(case.tags),
        }
        sql: LiteralString = 'SELECT "id" FROM "case" WHERE "name"=%(name)s'
        involved_id: int | None = None
        for record in self._select(sql, {"name": case.name}):
            involved_id = record["id"]
            params["id"] = record["id"]
            sql = """
                  UPDATE "case"
                  SET "updated"=%(now)s,
                      "name"=%(name)s,
                      "transcript"=%(transcript)s,
                      "limited_chart"=%(limited_chart)s,
                      "profile"=%(profile)s,
                      "validation_status"=%(validation_status)s,
                      "batch_identifier"=%(batch_identifier)s,
                      "tags"=%(tags)s
                  WHERE "id" = %(id)s
                    AND (
                      "name" != %(name)s OR
                          "transcript"::jsonb != %(transcript)s::jsonb OR
                          "limited_chart"::jsonb != %(limited_chart)s::jsonb OR
                          "profile" != %(profile)s OR
                          "validation_status" != %(validation_status)s OR
                          "batch_identifier" != %(batch_identifier)s OR
                          "tags"::jsonb != %(tags)s::jsonb
                      )"""
            break
        else:
            sql = """
                  INSERT INTO "case" ("created", "updated", "name", "transcript", "limited_chart", "profile",
                                      "validation_status", "batch_identifier", "tags")
                  VALUES (%(now)s, %(now)s, %(name)s, %(transcript)s, %(limited_chart)s, %(profile)s,
                          %(validation_status)s, %(batch_identifier)s, %(tags)s) RETURNING id"""

        return Record(
            id=self._alter(sql, params, involved_id),
            name=case.name,
            transcript=case.transcript,
            limited_chart=case.limited_chart,
            profile=case.profile,
            validation_status=case.validation_status,
            batch_identifier=case.batch_identifier,
            tags=case.tags,
        )
