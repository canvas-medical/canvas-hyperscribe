from datetime import datetime, UTC

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.structures.evaluation_case import EvaluationCase
from evaluations.structures.evaluation_result import EvaluationResult
from evaluations.structures.statistic_end2end import StatisticEnd2End
from evaluations.structures.statistic_test import StatisticTest


class StoreResults(Postgres):
    # this class is the bare minimum to access the PostgresSQL database and result table
    # it assumes that all involved objects (database, tables) are correctly
    # accessible with the provided credentials

    def insert(self, case: EvaluationCase, result: EvaluationResult) -> None:
        values = {
            "now": datetime.now(UTC),
            "uuid": result.run_uuid,
            "commit": result.commit_uuid,
            "type": case.case_type,
            "group": case.case_group,
            "name": case.case_name,
            "cycles": case.cycles,
            "cycle": result.cycle,
            "test": result.test_name,
            "duration": result.milliseconds,
            "passed": result.passed,
            "errors": result.errors,
        }
        sql = """
              INSERT INTO "results" ("created", "run_uuid", "plugin_commit", "case_type", "case_group", "case_name",
                                     "cycles", "cycle", "test_name", "milliseconds", "passed", "errors")
              VALUES (%(now)s, %(uuid)s, %(commit)s, %(type)s, %(group)s, %(name)s,
                      %(cycles)s, %(cycle)s, %(test)s, %(duration)s, %(passed)s, %(errors)s)"""
        self._alter(sql, values, None)

    def statistics_per_test(self) -> list[StatisticTest]:
        sql = """
              SELECT "case_name", "test_name", SUM(CASE WHEN "passed" = True THEN 1 ELSE 0 END) / "cycles" AS "passed_count"
              FROM "results"
              WHERE "cycles" > 0
              GROUP BY "case_name", "test_name", "cycles"
              ORDER BY 1, 2"""
        return [
            StatisticTest(
                case_name=record['case_name'],
                test_name=record['test_name'],
                passed_count=record['passed_count'],
            )
            for record in self._select(sql, {})
        ]

    def statistics_end2end(self) -> list[StatisticEnd2End]:
        sql = """
              SELECT "case_name", SUM("full_run") AS "full_run", SUM("full_passed") AS "end2end", COUNT(distinct "run_uuid") AS "run_count"
              FROM (SELECT "case_name",
                           "run_uuid",
                           (CASE WHEN SUM(CASE WHEN "passed" = True THEN 1 ELSE 0 END) = COUNT(1) THEN 1 ELSE 0 END) AS "full_passed",
                           (CASE WHEN MAX("cycle") = -1 THEN 1 ELSE 0 END)                                           AS "full_run"
                    FROM "results"
                    GROUP BY "case_name", "run_uuid")
              GROUP BY "case_name"
              ORDER BY 1"""
        return [
            StatisticEnd2End(
                case_name=record["case_name"],
                run_count=record["run_count"],
                full_run=record["full_run"],
                end2end=record["end2end"],
            )
            for record in self._select(sql, {})
        ]
