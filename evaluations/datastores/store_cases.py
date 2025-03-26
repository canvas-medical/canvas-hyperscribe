import sqlite3
from datetime import datetime
from pathlib import Path

from evaluations.constants import Constants
from evaluations.structures.evaluation_case import EvaluationCase


class StoreCases:

    @classmethod
    def _create_table_sql(cls) -> str:
        return ("CREATE TABLE IF NOT EXISTS cases ("
                "`id` INTEGER PRIMARY KEY AUTOINCREMENT,"
                "`created` DATETIME NOT NULL,"
                "`updated` DATETIME NOT NULL,"
                "`environment` TEXT NOT NULL,"
                "`patient_uuid` TEXT NOT NULL,"
                "`case_type` TEXT NOT NULL,"
                "`case_group` TEXT NOT NULL,"
                "`case_name` TEXT NOT NULL,"
                "`description` TEXT NOT NULL)")

    @classmethod
    def _update_sql(cls) -> str:
        return ("UPDATE `cases` "
                "SET `updated`=:now,`environment`=:environment,`patient_uuid`=:patient,"
                "`case_type`=:type,`case_group`=:group,`description`=:description "
                "WHERE `case_name`=:name")

    @classmethod
    def _insert_sql(cls) -> str:
        return ("INSERT INTO `cases` (`created`,`updated`,`environment`,`patient_uuid`,`case_type`,`case_group`,`case_name`,`description`) "
                "VALUES (:now, :now, :environment, :patient, :type, :group, :name, :description)")

    @classmethod
    def _select_sql(cls) -> str:
        return ("SELECT `environment`,`patient_uuid`,`case_type`,`case_group`,`case_name`,`description` "
                "FROM `cases` "
                "WHERE `case_name`=:name")

    @classmethod
    def _delete_sql(cls) -> str:
        return "DELETE FROM `cases` WHERE `case_name`=:name"

    @classmethod
    def _db_path(cls) -> Path:
        return Path(__file__).parent.parent / "evaluation_cases.db"

    @classmethod
    def upsert(cls, case: EvaluationCase) -> None:
        now = datetime.now()
        parameter = {
            "now": now,
            "environment": case.environment,
            "patient": case.patient_uuid,
            "type": case.case_type,
            "group": case.case_group,
            "description": case.description,
            "name": case.case_name,
        }
        with sqlite3.connect(cls._db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute(cls._create_table_sql())
            cursor.execute(cls._update_sql(), parameter)
            if cursor.rowcount == 0:  # no rows were updated -> insert a new record
                cursor.execute(cls._insert_sql(), parameter)
            conn.commit()

    @classmethod
    def delete(cls, case_name: str) -> None:
        with sqlite3.connect(cls._db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute(cls._create_table_sql())
            cursor.execute(cls._delete_sql(), {"name": case_name})
            conn.commit()

    @classmethod
    def get(cls, case_name: str) -> EvaluationCase:
        result = EvaluationCase(
            case_type=Constants.TYPE_GENERAL,
            case_group=Constants.GROUP_COMMON,
            case_name=case_name,
        )
        with sqlite3.connect(cls._db_path()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(cls._create_table_sql())
            cursor.execute(cls._select_sql(), {"name": case_name})
            if row := cursor.fetchone():
                result = EvaluationCase(
                    environment=row['environment'],
                    patient_uuid=row['patient_uuid'],
                    case_type=row['case_type'],
                    case_group=row['case_group'],
                    case_name=row['case_name'],
                    description=row['description'],
                )
        return result
