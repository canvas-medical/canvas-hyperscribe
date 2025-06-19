from datetime import datetime, UTC
from pathlib import Path

from evaluations.datastores.sqllite.store_base import StoreBase
from evaluations.structures.evaluation_case import EvaluationCase
from evaluations.structures.evaluation_result import EvaluationResult
from evaluations.structures.statistic_end2end import StatisticEnd2End
from evaluations.structures.statistic_test import StatisticTest


class StoreResults(StoreBase):
    @classmethod
    def _create_table_sql(cls) -> str:
        return ("CREATE TABLE IF NOT EXISTS results ("
                "`id` INTEGER PRIMARY KEY AUTOINCREMENT,"
                "`created` DATETIME NOT NULL,"
                "`run_uuid` TEXT NOT NULL,"  # <-- tests run identifier
                "`plugin_commit` TEXT NOT NULL,"
                "`case_type` TEXT NOT NULL,"
                "`case_group` TEXT NOT NULL,"
                "`case_name` TEXT NOT NULL,"
                "`cycles` INT NOT NULL,"
                "`cycle` INT NOT NULL,"
                "`test_name` TEXT NOT NULL,"
                "`milliseconds` REAL NOT NULL,"  # <-- duration of the test
                "`passed` INTEGER NOT NULL,"
                "`errors` TEXT NOT NULL)")

    @classmethod
    def _insert_sql(cls) -> str:
        return ("INSERT INTO results (`created`,`run_uuid`,`plugin_commit`,`case_type`,`case_group`,`case_name`,"
                "`cycles`,`cycle`,`test_name`,`milliseconds`,`passed`,`errors`) "
                "VALUES (:now,:uuid,:commit,:type,:group,:name,:cycles,:cycle,:test,:duration,:passed,:errors)")

    @classmethod
    def _db_path(cls) -> Path:
        return Path(__file__).parent.parent.parent.parent.parent / "evaluation_results.db"

    @classmethod
    def insert(cls, case: EvaluationCase, result: EvaluationResult) -> None:
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
        cls._insert(values)

    @classmethod
    def statistics_per_test(cls) -> list[StatisticTest]:
        sql = ("SELECT `case_name`,`test_name`,"
               "SUM(CASE WHEN `passed`=1 THEN 1 ELSE 0 END)/`cycles` AS `passed_count` "
               "FROM `results` "
               "WHERE `cycles`>0 "
               "GROUP BY `case_name`,`test_name`,`cycles`")

        return [
            StatisticTest(
                case_name=row['case_name'],
                test_name=row['test_name'],
                passed_count=row['passed_count'],
            )
            for row in cls._select(sql, {})
        ]

    @classmethod
    def statistics_end2end(cls) -> list[StatisticEnd2End]:
        sql = ("SELECT `case_name`,SUM(`full_run`) AS `full_run`,SUM(`full_passed`) AS `end2end`,COUNT(distinct `run_uuid`) AS `run_count` "
               "FROM (SELECT "
               " `case_name`, "
               " `run_uuid`, "
               " (CASE WHEN SUM(CASE WHEN `passed`=1 THEN 1 ELSE 0 END)=COUNT(1) THEN 1 ELSE 0 END) AS `full_passed`, "
               " (CASE WHEN MAX(`cycle`)=-1 THEN 1 ELSE 0 END) AS `full_run` "
               " FROM `results` "
               " GROUP BY `case_name`,`run_uuid`) "
               "GROUP BY `case_name`")
        return [
            StatisticEnd2End(
                case_name=row["case_name"],
                run_count=row["run_count"],
                full_run=row["full_run"],
                end2end=row["end2end"],
            )
            for row in cls._select(sql, {})
        ]
