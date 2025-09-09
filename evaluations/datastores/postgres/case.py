from datetime import datetime, UTC
from typing import LiteralString

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.records.case import Case as Record
from hyperscribe.structures.line import Line


class Case(Postgres):
    # def delete(self, case: str) -> None:
    #     sql: LiteralString = """
    #                          DELETE
    #                          FROM "case"
    #                          WHERE "name" = %(name)s RETURNING "id" """
    #     self._alter(sql, {"name": case}, None)

    def all_names(self) -> list[str]:
        sql: LiteralString = """
                             SELECT "name"
                             FROM "case"
                             ORDER BY "name" """
        return [record["name"] for record in self._select(sql, {})]

    def get_first_n_cases(self, n: int) -> list[str]:
        sql: LiteralString = """
                             SELECT "name"
                             FROM "case"
                             ORDER BY "id"
                             LIMIT %(limit)s """
        return [record["name"] for record in self._select(sql, {"limit": n})]

    def get_id(self, name: str) -> int:
        sql: LiteralString = """
                             SELECT "id"
                             FROM "case"
                             WHERE "name" = %(name)s"""
        for record in self._select(sql, {"name": name}):
            return int(record["id"])
        return 0

    def get_limited_chart(self, case_id: int) -> dict:
        sql: LiteralString = """
                             SELECT "limited_chart"
                             FROM "case"
                             WHERE "id" = %(case_id)s"""
        for record in self._select(sql, {"case_id": case_id}):
            return dict(record["limited_chart"])
        return {}

    def get_transcript(self, case_id: int) -> dict[str, list[Line]]:
        sql: LiteralString = """
                             SELECT "transcript"
                             FROM "case"
                             WHERE "id" = %(case_id)s"""
        for record in self._select(sql, {"case_id": case_id}):
            return {cycle_key: Line.load_from_json(lines) for cycle_key, lines in record["transcript"].items()}
        return {}

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
            "transcript": self.constant_dumps(
                {key: [line.to_json() for line in lines] for key, lines in case.transcript.items()},
            ),
            "limited_chart": self.constant_dumps(
                case.limited_chart if isinstance(case.limited_chart, dict) else case.limited_chart.to_json()
            ),
            "profile": case.profile,
            "validation_status": case.validation_status.value,
            "batch_identifier": case.batch_identifier,
            "tags": self.constant_dumps(case.tags),
        }
        sql: LiteralString = 'SELECT "id" FROM "case" WHERE "name"=%(name)s'
        involved_id: int | None = None
        for record in self._select(sql, {"name": case.name}):
            involved_id = record["id"]
            params["id"] = record["id"]
            for field in ["transcript", "limited_chart", "tags"]:
                params[f"{field}_md5"] = self.md5_from(str(params[field]))

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
                          MD5("transcript"::text) != %(transcript_md5)s OR
                          MD5("limited_chart"::text) != %(limited_chart_md5)s OR
                          "profile" != %(profile)s OR
                          "validation_status" != %(validation_status)s OR
                          "batch_identifier" != %(batch_identifier)s OR
                          MD5("tags"::text) != %(tags_md5)s
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

    def update_fields(self, case_id: int, updates: dict) -> None:
        self._update_fields("case", Record, case_id, updates)
