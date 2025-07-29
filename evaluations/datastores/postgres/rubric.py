from datetime import datetime, UTC
from typing import LiteralString, cast

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.records.rubric import Rubric as RubricRecord


class Rubric(Postgres):
    def upsert(self, rubric: RubricRecord) -> RubricRecord:
        params = {
            "now": datetime.now(UTC),
            "case_id": rubric.case_id,
            "parent_rubric_id": rubric.parent_rubric_id,
            "validation_timestamp": rubric.validation_timestamp,
            "validation": rubric.validation.value,
            "author": rubric.author,
            "rubric": self.constant_dumps(rubric.rubric),
            "case_provenance_classification": rubric.case_provenance_classification,
            "comments": rubric.comments,
            "text_llm_vendor": rubric.text_llm_vendor,
            "text_llm_name": rubric.text_llm_name,
            "temperature": rubric.temperature,
        }

        sql: LiteralString = 'SELECT "id" FROM "rubric" WHERE "case_id" = %(case_id)s'
        involved_id: int | None = None
        for record in self._select(sql, {"case_id": rubric.case_id}):
            involved_id = record["id"]
            params["id"] = involved_id
            sql = """
                UPDATE "rubric"
                SET "updated" = %(now)s,
                    "parent_rubric_id" = %(parent_rubric_id)s,
                    "validation_timestamp" = %(validation_timestamp)s,
                    "validation" = %(validation)s,
                    "author" = %(author)s,
                    "rubric" = %(rubric)s,
                    "case_provenance_classification" = %(case_provenance_classification)s,
                    "comments" = %(comments)s,
                    "text_llm_vendor" = %(text_llm_vendor)s,
                    "text_llm_name" = %(text_llm_name)s,
                    "temperature" = %(temperature)s
                WHERE "id" = %(id)s
            """
            break
        else:
            sql = """
                INSERT INTO "rubric" (
                    "created", "updated", "case_id", "parent_rubric_id", "validation_timestamp",
                    "validation", "author", "rubric", "case_provenance_classification",
                    "comments", "text_llm_vendor", "text_llm_name", "temperature"
                )
                VALUES (
                    %(now)s, %(now)s, %(case_id)s, %(parent_rubric_id)s, %(validation_timestamp)s,
                    %(validation)s, %(author)s, %(rubric)s, %(case_provenance_classification)s,
                    %(comments)s, %(text_llm_vendor)s, %(text_llm_name)s, %(temperature)s
                )
                RETURNING id
            """

        return RubricRecord(
            id=self._alter(sql, params, involved_id),
            case_id=rubric.case_id,
            parent_rubric_id=rubric.parent_rubric_id,
            validation_timestamp=rubric.validation_timestamp,
            validation=rubric.validation,
            author=rubric.author,
            rubric=rubric.rubric,
            case_provenance_classification=rubric.case_provenance_classification,
            comments=rubric.comments,
            text_llm_vendor=rubric.text_llm_vendor,
            text_llm_name=rubric.text_llm_name,
            temperature=rubric.temperature,
        )

    def get_rubric(self, rubric_id: int) -> list[dict]:
        """Get the rubric content for a given rubric ID."""
        sql: LiteralString = 'SELECT "rubric" FROM "rubric" WHERE "id" = %(id)s'
        for record in self._select(sql, {"id": rubric_id}):
            return cast(list[dict], record["rubric"])
        return []
