import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from evaluations.datastores.store_cases import StoreCases
from evaluations.structures.evaluation_result import EvaluationResult
from evaluations.structures.statistic_case_test import StatisticCaseTest


class StoreResults:
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
                "`test_name` TEXT NOT NULL,"
                "`milliseconds` REAL NOT NULL,"  # <-- duration of the test
                "`passed` INTEGER NOT NULL,"
                "`errors` TEXT NOT NULL)")

    @classmethod
    def _insert_sql(cls) -> str:
        return ("INSERT INTO results (`created`,`run_uuid`,`plugin_commit`,`case_type`,`case_group`,`case_name`,"
                "`test_name`,`milliseconds`,`passed`,`errors`) "
                "VALUES (:now,:uuid,:commit,:type,:group,:name,:test,:duration,:passed,:errors)")

    @classmethod
    def _db_path(cls) -> Path:
        return Path(__file__).parent.parent.parent.parent / "evaluation_results.db"

    @classmethod
    def insert(cls, run_uuid: uuid, plugin_commit: str, result: EvaluationResult):
        now = datetime.now()
        case = StoreCases.get(result.test_case)
        parameter = {
            "now": now,
            "uuid": str(run_uuid),
            "commit": plugin_commit,
            "type": case.case_type,
            "group": case.case_group,
            "name": case.case_name,
            "test": result.test_name,
            "duration": result.milliseconds,
            "passed": int(result.passed),
            "errors": result.errors,
        }
        with sqlite3.connect(cls._db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute(cls._create_table_sql())
            cursor.execute(cls._insert_sql(), parameter)
            conn.commit()

    @classmethod
    def case_test_statistics(cls) -> list[StatisticCaseTest]:
        with sqlite3.connect(cls._db_path()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(cls._create_table_sql())

            result: dict[str, StatisticCaseTest] = {}
            #
            sql = ("SELECT `case_name`,`test_name`,"
                   "SUM(CASE WHEN `passed`=1 THEN 1 ELSE 0 END) AS `passed_count` "
                   "FROM `results` "
                   "GROUP BY `case_name`,`test_name`")

            cursor.execute(sql)
            for row in cursor.fetchall():
                if row["case_name"] not in result:
                    result[row["case_name"]] = StatisticCaseTest(case_name=row['case_name'])
                if hasattr(result[row["case_name"]], row['test_name']):
                    setattr(result[row["case_name"]], row['test_name'], row['passed_count'])
            #
            sql = ("SELECT `case_name`,SUM(`full_passed`) AS `end2end`,COUNT(distinct `run_uuid`) AS `run_count` "
                   "FROM (SELECT "
                   " `case_name`, "
                   " `run_uuid`, "
                   " (CASE WHEN SUM(CASE WHEN `passed`=1 THEN 1 ELSE 0 END)=COUNT(1) THEN 1 ELSE 0 END) AS `full_passed` "
                   " FROM `results` "
                   " GROUP BY `case_name`,`run_uuid`) "
                   "GROUP BY `case_name`")
            cursor.execute(sql)
            for row in cursor.fetchall():
                result[row["case_name"]].run_count = row["run_count"]
                result[row["case_name"]].end2end = row["end2end"]

            return list(result.values())
