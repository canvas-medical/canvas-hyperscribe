from datetime import datetime, UTC
from typing import LiteralString

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.experiment_models import ExperimentModels
from evaluations.structures.records.case_id import CaseId as CaseIdRecord
from evaluations.structures.records.experiment import Experiment as Record
from evaluations.structures.records.model import Model as ModelRecord


class Experiment(Postgres):
    def get_experiment(self, experiment_id: int) -> Record:
        sql: LiteralString = """
                             SELECT "id",
                                    "name",
                                    "cycle_times",
                                    "cycle_transcript_overlaps",
                                    "note_replications",
                                    "grade_replications"
                             FROM "experiment"
                             WHERE "id" = %(id)s
                             """
        for record in self._select(sql, {"id": experiment_id}):
            return Record(
                id=record["id"],
                name=record["name"],
                cycle_times=record["cycle_times"],
                cycle_transcript_overlaps=record["cycle_transcript_overlaps"],
                note_replications=record["note_replications"],
                grade_replications=record["grade_replications"],
            )
        return Record()

    def get_cases(self, experiment_id: int) -> list[CaseIdRecord]:
        sql: LiteralString = """
                             SELECT c."id", c."name"
                             FROM "experiment_case" ec
                                      JOIN "case" c ON ec."case_id" = c."id"
                             WHERE ec."experiment_id" = %(experiment_id)s
                             ORDER BY c."id"
                             """

        return [
            CaseIdRecord(
                id=record["id"],
                name=record["name"],
            )
            for record in self._select(sql, {"experiment_id": experiment_id})
        ]

    def get_models(self, experiment_id: int) -> list[ExperimentModels]:
        sql: LiteralString = """
                             SELECT n."id"                              as "generator_id",
                                    n."vendor"                          as "generator_vendor",
                                    n."api_key"                         as "generator_api_key",
                                    g."id"                              as "grader_id",
                                    g."vendor"                          as "grader_vendor",
                                    g."api_key"                         as "grader_api_key",
                                    em."model_note_grader_is_reasoning" as "is_reasoning"
                             FROM "experiment_model" em
                                      JOIN "model" n ON em."model_note_generator_id" = n."id"
                                      JOIN "model" g ON em."model_note_grader_id" = g."id"
                             WHERE em."experiment_id" = %(experiment_id)s
                             ORDER BY n."id", g."id"
                             """

        return [
            ExperimentModels(
                experiment_id=experiment_id,
                model_generator=ModelRecord(
                    id=record["generator_id"],
                    vendor=record["generator_vendor"],
                    api_key=record["generator_api_key"],
                ),
                model_grader=ModelRecord(
                    id=record["grader_id"],
                    vendor=record["grader_vendor"],
                    api_key=record["grader_api_key"],
                ),
                grader_is_reasoning=record["is_reasoning"],
            )
            for record in self._select(sql, {"experiment_id": experiment_id})
        ]

    def upsert(self, experiment: Record) -> Record:
        params = {
            "now": datetime.now(UTC),
            "name": experiment.name,
            "cycle_times": self.constant_dumps(experiment.cycle_times),
            "cycle_transcript_overlaps": self.constant_dumps(experiment.cycle_transcript_overlaps),
            "note_replications": experiment.note_replications,
            "grade_replications": experiment.grade_replications,
        }
        sql: LiteralString = 'SELECT "id" FROM "experiment" WHERE "name"=%(name)s'
        involved_id: int | None = None
        for record in self._select(sql, {"name": experiment.name}):
            involved_id = record["id"]
            params["id"] = record["id"]
            for field in ["cycle_times", "cycle_transcript_overlaps"]:
                params[f"{field}_md5"] = self.md5_from(str(params[field]))

            sql = """
                  UPDATE "experiment"
                  SET "updated"=%(now)s,
                      "cycle_times"=%(cycle_times)s,
                      "cycle_transcript_overlaps"=%(cycle_transcript_overlaps)s,
                      "note_replications"=%(note_replications)s,
                      "grade_replications"=%(grade_replications)s
                  WHERE "id" = %(id)s
                    AND (
                      MD5("cycle_times"::text) != %(cycle_times_md5)s OR
                          MD5("cycle_transcript_overlaps"::text) != %(cycle_transcript_overlaps_md5)s OR
                          "note_replications" != %(note_replications)s OR
                          "grade_replications" != %(grade_replications)s
                      )"""
            break
        else:
            sql = """
                  INSERT INTO "experiment" ("created", "updated", "name",
                                            "cycle_times", "cycle_transcript_overlaps",
                                            "note_replications", "grade_replications")
                  VALUES (%(now)s, %(now)s, %(name)s,
                          %(cycle_times)s, %(cycle_transcript_overlaps)s,
                          %(note_replications)s, %(grade_replications)s) RETURNING id"""
        return Record(
            id=self._alter(sql, params, involved_id),
            name=experiment.name,
            cycle_times=experiment.cycle_times,
            cycle_transcript_overlaps=experiment.cycle_transcript_overlaps,
            note_replications=experiment.note_replications,
            grade_replications=experiment.grade_replications,
        )

    def add_case(self, experiment_id: int, case_id: int) -> int:
        params = {
            "now": datetime.now(UTC),
            "experiment_id": experiment_id,
            "case_id": case_id,
        }
        sql: LiteralString = """
                             SELECT "id"
                             FROM "experiment_case"
                             WHERE "experiment_id" = %(experiment_id)s
                               AND "case_id" = %(case_id)s
                             """
        for record in self._select(sql, params):
            result = int(record["id"])
            break
        else:
            sql = """
                  INSERT INTO "experiment_case"("created", "experiment_id", "case_id")
                  VALUES (%(now)s, %(experiment_id)s, %(case_id)s) RETURNING id
                  """
            result = self._alter(sql, params, None)
        return result

    def add_model(self, experiment_id: int, model_id: int) -> int:
        params = {
            "now": datetime.now(UTC),
            "experiment_id": experiment_id,
            "model_id": model_id,
        }
        sql: LiteralString = """
                             SELECT "id"
                             FROM "experiment_model"
                             WHERE "experiment_id" = %(experiment_id)s
                               AND "model_id" = %(model_id)s
                             """
        for record in self._select(sql, params):
            result = int(record["id"])
            break
        else:
            sql = """
                  INSERT INTO "experiment_model"("created", "experiment_id", "model_id")
                  VALUES (%(now)s, %(experiment_id)s, %(model_id)s) RETURNING id
                  """
            result = self._alter(sql, params, None)
        return result

    def update_fields(self, experiment_id: int, updates: dict) -> None:
        self._update_fields("experiment", Record, experiment_id, updates)
