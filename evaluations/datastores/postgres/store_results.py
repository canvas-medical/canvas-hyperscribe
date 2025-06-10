from datetime import datetime, UTC
from typing import Generator

from psycopg import connect, sql as sqlist

from evaluations.structures.evaluation_case import EvaluationCase
from evaluations.structures.evaluation_result import EvaluationResult
from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.structures.statistic_end2end import StatisticEnd2End
from evaluations.structures.statistic_test import StatisticTest


class StoreResults:
    # this class is the bare minimum to access the PostgresSQL database and result table
    # it assumes that all involved objects (database, tables) are correctly
    # accessible with the provided credentials

    def __init__(self, credentials: PostgresCredentials):
        self.credentials = credentials

    def insert(self, case: EvaluationCase, result: EvaluationResult) -> None:
        sql = sqlist.SQL("""
INSERT INTO "results" ("created","run_uuid","plugin_commit","case_type","case_group","case_name","test_name","milliseconds","passed","errors")
VALUES (%(now)s,%(uuid)s,%(commit)s,%(type)s,%(group)s,%(name)s,%(test)s,%(duration)s,%(passed)s,%(errors)s)
""")
        values = {
            "now": datetime.now(UTC),
            "uuid": result.run_uuid,
            "commit": result.commit_uuid,
            "type": case.case_type,
            "group": case.case_group,
            "name": case.case_name,
            "test": result.test_name,
            "duration": result.milliseconds,
            "passed": result.passed,
            "errors": result.errors,
        }
        with connect(
                dbname=self.credentials.database,
                host=self.credentials.host,
                user=self.credentials.user,
                password=self.credentials.password,
                port=self.credentials.port,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, values)
                connection.commit()

    def _select(self, sql: sqlist.SQL, params: dict) -> Generator[dict, None, None]:
        with connect(
                dbname=self.credentials.database,
                host=self.credentials.host,
                user=self.credentials.user,
                password=self.credentials.password,
                port=self.credentials.port,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                column_names = [desc[0] for desc in cursor.description or []]
                for row in cursor.fetchall():
                    yield dict(zip(column_names, row))
                connection.commit()

    def statistics_per_test(self) -> list[StatisticTest]:
        sql = sqlist.SQL("""
SELECT "case_name","test_name",SUM(CASE WHEN "passed"=True THEN 1 ELSE 0 END) AS "passed_count"
FROM "results"
GROUP BY "case_name","test_name"
ORDER BY 1, 2
""")
        return [
            StatisticTest(
                case_name=record['case_name'],
                test_name=record['test_name'],
                passed_count=record['passed_count'],
            )
            for record in self._select(sql, {})
        ]

    def statistics_end2end(self) -> list[StatisticEnd2End]:
        sql = sqlist.SQL("""
SELECT "case_name",SUM("full_passed") AS "end2end",COUNT(distinct "run_uuid") AS "run_count" 
FROM (SELECT 
 "case_name", 
 "run_uuid", 
 (CASE WHEN SUM(CASE WHEN "passed"=True THEN 1 ELSE 0 END)=COUNT(1) THEN 1 ELSE 0 END) AS "full_passed" 
 FROM "results" 
 GROUP BY "case_name","run_uuid") 
GROUP BY "case_name"
ORDER BY 1
""")
        return [
            StatisticEnd2End(
                case_name=record["case_name"],
                run_count=record["run_count"],
                end2end=record["end2end"],
            )
            for record in self._select(sql, {})
        ]
