from datetime import datetime, UTC
from pathlib import Path

from evaluations.constants import Constants
from evaluations.datastores.sqllite.store_base import StoreBase
from evaluations.structures.evaluation_case import EvaluationCase


class StoreCases(StoreBase):

    @classmethod
    def _create_table_sql(cls) -> str:
        return ("CREATE TABLE IF NOT EXISTS cases ("
                "`id` INTEGER PRIMARY KEY AUTOINCREMENT,"
                "`created` DATETIME NOT NULL,"
                "`updated` DATETIME NOT NULL,"
                "`environment` TEXT NOT NULL,"
                "`patient_uuid` TEXT NOT NULL,"
                "`limited_cache` TEXT NOT NULL,"
                "`case_type` TEXT NOT NULL,"
                "`case_group` TEXT NOT NULL,"
                "`case_name` TEXT NOT NULL,"
                "`description` TEXT NOT NULL)")

    @classmethod
    def _update_sql(cls) -> str:
        return ("UPDATE `cases` "
                "SET `updated`=:now,`environment`=:environment,`patient_uuid`=:patient,`limited_cache`=:cache,"
                "`case_type`=:type,`case_group`=:group,`description`=:description "
                "WHERE `case_name`=:name")

    @classmethod
    def _insert_sql(cls) -> str:
        return (
            "INSERT INTO `cases` (`created`,`updated`,`environment`,`patient_uuid`,`limited_cache`,`case_type`,`case_group`,`case_name`,`description`) "
            "VALUES (:now,:now,:environment,:patient,:cache,:type,:group,:name,:description)")

    @classmethod
    def _delete_sql(cls) -> str:
        return "DELETE FROM `cases` WHERE `case_name`=:name"

    @classmethod
    def _db_path(cls) -> Path:
        return Path(__file__).parent.parent.parent / "evaluation_cases.db"

    @classmethod
    def upsert(cls, case: EvaluationCase) -> None:
        now = datetime.now(UTC)
        parameters = {
            "now": now,
            "environment": case.environment,
            "patient": case.patient_uuid,
            "cache": case.limited_cache,
            "type": case.case_type,
            "group": case.case_group,
            "description": case.description,
            "name": case.case_name,
        }
        cls._upsert(parameters)

    @classmethod
    def delete(cls, case_name: str) -> None:
        cls._delete({"name": case_name})

    @classmethod
    def get(cls, case_name: str) -> EvaluationCase:
        result = EvaluationCase(
            case_type=Constants.TYPE_GENERAL,
            case_group=Constants.GROUP_COMMON,
            case_name=case_name,
        )
        sql = ("SELECT `environment`,`patient_uuid`,`limited_cache`,`case_type`,`case_group`,`case_name`,`description` "
               "FROM `cases` "
               "WHERE `case_name`=:name")
        for row in cls._select(sql, {"name": case_name}):
            result = EvaluationCase(**dict(row))
        return result

    @classmethod
    def all(cls) -> list[EvaluationCase]:
        sql = ("SELECT `environment`,`patient_uuid`,`case_type`,`case_group`,`case_name`,`description` "
               "FROM `cases` "
               "ORDER BY 3")
        return [
            EvaluationCase(**dict(row))
            for row in cls._select(sql, {})
        ]
