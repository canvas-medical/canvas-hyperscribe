from datetime import datetime, UTC
from typing import LiteralString, cast

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.enums.rubric_validation import RubricValidation
from evaluations.structures.records.rubric import Rubric as RubricRecord


class Rubric(Postgres):
    def insert(self, rubric: RubricRecord) -> RubricRecord:
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
        sql: LiteralString = """
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
            id=self._alter(sql, params, None),
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

    def upsert(self, rubric: RubricRecord) -> RubricRecord:
        sql: LiteralString = 'SELECT "id" FROM "rubric" WHERE "case_id" = %(case_id)s'
        for record in self._select(sql, {"case_id": rubric.case_id}):
            # Update existing record
            involved_id = record["id"]
            params = {
                "now": datetime.now(UTC),
                "id": involved_id,
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
        else:
            # Insert new record using the insert method
            return self.insert(rubric)

    def get_rubric(self, rubric_id: int) -> list[dict]:
        """Get the rubric content for a given rubric ID."""
        sql: LiteralString = 'SELECT "rubric" FROM "rubric" WHERE "id" = %(id)s'
        for record in self._select(sql, {"id": rubric_id}):
            return cast(list[dict], record["rubric"])
        return []

    def get_last_accepted(self, case_id: int) -> list[int]:
        sql: LiteralString = """
                             WITH latest_by_author AS (SELECT DISTINCT
                             ON (author)
                                 id as rubric_id,
                                 author,
                                 validation_timestamp
                             FROM rubric
                             WHERE case_id = %(case_id)s
                               AND validation = %(accepted)s
                               AND author LIKE %(email_like)s
                             ORDER BY author, validation_timestamp DESC
                                 )
                             SELECT rubric_id
                             FROM latest_by_author
                             ORDER BY validation_timestamp DESC
                             """
        params = {
            "case_id": case_id,
            "accepted": RubricValidation.ACCEPTED.value,
            "email_like": "%@%",
        }
        result: list[int] = []
        for record in self._select(sql, params):
            result.append(int(record["rubric_id"]))
        return result
