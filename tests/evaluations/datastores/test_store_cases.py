import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import patch, call

from evaluations.datastores.store_cases import StoreCases
from evaluations.structures.evaluation_case import EvaluationCase


def test__create_table_sql():
    tested = StoreCases
    result = tested._create_table_sql()
    expected = ("CREATE TABLE IF NOT EXISTS cases ("
                "`id` INTEGER PRIMARY KEY AUTOINCREMENT,"
                "`created` DATETIME NOT NULL,"
                "`updated` DATETIME NOT NULL,"
                "`environment` TEXT NOT NULL,"
                "`patient_uuid` TEXT NOT NULL,"
                "`case_type` TEXT NOT NULL,"
                "`case_group` TEXT NOT NULL,"
                "`case_name` TEXT NOT NULL,"
                "`description` TEXT NOT NULL)")
    assert result == expected


def test__update_sql():
    tested = StoreCases
    result = tested._update_sql()
    expected = ("UPDATE `cases` "
                "SET `updated`=:now,`environment`=:environment,`patient_uuid`=:patient,"
                "`case_type`=:type,`case_group`=:group,`description`=:description "
                "WHERE `case_name`=:name")
    assert result == expected


def test__insert_sql():
    tested = StoreCases
    result = tested._insert_sql()
    expected = ("INSERT INTO `cases` (`created`,`updated`,`environment`,`patient_uuid`,`case_type`,`case_group`,`case_name`,`description`) "
                "VALUES (:now, :now, :environment, :patient, :type, :group, :name, :description)")
    assert result == expected


def test__select_sql():
    tested = StoreCases
    result = tested._select_sql()
    expected = ("SELECT `environment`,`patient_uuid`,`case_type`,`case_group`,`case_name`,`description` "
                "FROM `cases` "
                "WHERE `case_name`=:name")
    assert result == expected


def test__delete_sql():
    tested = StoreCases
    result = tested._delete_sql()
    expected = "DELETE FROM `cases` WHERE `case_name`=:name"
    assert result == expected


def test__db_path():
    tested = StoreCases
    with patch('evaluations.datastores.store_cases.Path') as mock_path:
        mock_path.side_effect = [Path('/a/b/c/d/e/f/g/theFile.py')]
        result = tested._db_path()
        assert result == Path('/a/b/c/d/e/f/evaluation_cases.db')


@patch("evaluations.datastores.store_cases.datetime", wraps=datetime)
@patch.object(StoreCases, "_db_path")
def test_upsert(db_path, mock_datetime):
    def reset_mocks():
        db_path.reset_mock()
        mock_datetime.reset_mock()

    cases = [
        EvaluationCase(
            environment="theEnvironment1",
            patient_uuid="thePatientUuid1",
            case_type="theType1",
            case_group="theGroup1",
            case_name="theCaseName1",
            description="theDescription1",
        ),
        EvaluationCase(
            environment="theEnvironment2",
            patient_uuid="thePatientUuid2",
            case_type="theType2",
            case_group="theGroup2",
            case_name="theCaseName2",
            description="theDescription2",
        ),
        EvaluationCase(
            environment="theEnvironment3",
            patient_uuid="thePatientUuid3",
            case_type="theType3",
            case_group="theGroup3",
            case_name="theCaseName1",  # <-- for update
            description="theDescription3",
        ),
    ]
    dates = [
        datetime(2025, 3, 26, 11, 38, 21, 123456, tzinfo=timezone.utc),
        datetime(2025, 3, 26, 11, 38, 24, 321456, tzinfo=timezone.utc),
        datetime(2025, 3, 26, 11, 38, 32, 452361, tzinfo=timezone.utc),
        datetime(2025, 3, 26, 11, 38, 33, 452365, tzinfo=timezone.utc),
    ]
    tested = StoreCases
    with NamedTemporaryFile(delete=True) as temp_file:
        db_path.return_value = Path(temp_file.name)

        # record does not exist yet
        case_db = tested.get("theCaseName1")
        case_exp = EvaluationCase(
            environment="",
            patient_uuid="",
            case_type="general",
            case_group="common",
            case_name="theCaseName1",
            description="",
        )
        assert case_db == case_exp
        reset_mocks()

        mock_datetime.now.side_effect = dates
        # create records
        tested.upsert(cases[0])
        calls = [call()]
        assert db_path.mock_calls == calls
        calls = [call.now()]
        assert mock_datetime.mock_calls == calls
        reset_mocks()
        tested.upsert(cases[1])
        calls = [call()]
        assert db_path.mock_calls == calls
        calls = [call.now()]
        assert mock_datetime.mock_calls == calls
        reset_mocks()
        # retrieve the records
        case_db = tested.get("theCaseName1")
        assert case_db == cases[0]
        case_db = tested.get("theCaseName2")
        assert case_db == cases[1]
        reset_mocks()

        # update records
        tested.upsert(cases[2])
        calls = [call()]
        assert db_path.mock_calls == calls
        calls = [call.now()]
        assert mock_datetime.mock_calls == calls
        reset_mocks()
        tested.upsert(cases[1])
        calls = [call()]
        assert db_path.mock_calls == calls
        calls = [call.now()]
        assert mock_datetime.mock_calls == calls
        reset_mocks()
        # retrieve the records
        case_db = tested.get("theCaseName1")
        assert case_db == cases[2]
        case_db = tested.get("theCaseName2")
        assert case_db == cases[1]
        reset_mocks()

        with sqlite3.connect(temp_file.name) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM `cases`")
            result = [
                {
                    "id": r["id"],
                    "created": r["created"],
                    "updated": r["updated"],
                    "environment": r["environment"],
                    "patient_uuid": r["patient_uuid"],
                    "case_type": r["case_type"],
                    "case_group": r["case_group"],
                    "case_name": r["case_name"],
                    "description": r["description"],
                }
                for r in cursor.fetchall()
            ]
            expected = [
                {
                    "id": 1,
                    "case_group": "theGroup3",
                    "case_name": "theCaseName1",
                    "case_type": "theType3",
                    "created": "2025-03-26 11:38:21.123456+00:00",
                    "description": "theDescription3",
                    "environment": "theEnvironment3",
                    "patient_uuid": "thePatientUuid3",
                    "updated": "2025-03-26 11:38:32.452361+00:00",
                },
                {
                    "id": 2,
                    "case_group": "theGroup2",
                    "case_name": "theCaseName2",
                    "case_type": "theType2",
                    "created": "2025-03-26 11:38:24.321456+00:00",
                    "description": "theDescription2",
                    "environment": "theEnvironment2",
                    "patient_uuid": "thePatientUuid2",
                    "updated": "2025-03-26 11:38:33.452365+00:00",
                },
            ]
            assert result == expected


@patch.object(StoreCases, "_db_path")
def test_delete(db_path):
    def reset_mocks():
        db_path.reset_mock()

    cases = [
        EvaluationCase(
            environment="theEnvironment1",
            patient_uuid="thePatientUuid1",
            case_type="theType1",
            case_group="theGroup1",
            case_name="theCaseName1",
            description="theDescription1",
        ),
        EvaluationCase(
            environment="theEnvironment2",
            patient_uuid="thePatientUuid2",
            case_type="theType2",
            case_group="theGroup2",
            case_name="theCaseName2",
            description="theDescription2",
        ),
    ]
    tested = StoreCases
    with NamedTemporaryFile(delete=True) as temp_file:
        db_path.return_value = Path(temp_file.name)

        case_exps = [
            EvaluationCase(
                environment="",
                patient_uuid="",
                case_type="general",
                case_group="common",
                case_name="theCaseName1",
                description="",
            ),
            EvaluationCase(
                environment="",
                patient_uuid="",
                case_type="general",
                case_group="common",
                case_name="theCaseName2",
                description="",
            ),
        ]
        # record does not exist yet
        case_db = tested.get("theCaseName1")
        assert case_db == case_exps[0]
        case_db = tested.get("theCaseName2")
        assert case_db == case_exps[1]

        # create records
        tested.upsert(cases[0])
        tested.upsert(cases[1])
        # retrieve the records
        case_db = tested.get("theCaseName1")
        assert case_db == cases[0]
        case_db = tested.get("theCaseName2")
        assert case_db == cases[1]

        # delete record
        tested.delete("theCaseName1")
        # retrieve the records
        case_db = tested.get("theCaseName1")
        assert case_db == case_exps[0]
        case_db = tested.get("theCaseName2")
        assert case_db == cases[1]

        # delete record
        tested.delete("theCaseName2")
        # retrieve the records
        case_db = tested.get("theCaseName1")
        assert case_db == case_exps[0]
        case_db = tested.get("theCaseName2")
        assert case_db == case_exps[1]

        calls = [call()] * 12
        assert db_path.mock_calls == calls
        reset_mocks()


@patch.object(StoreCases, "_db_path")
def test_get(db_path):
    def reset_mocks():
        db_path.reset_mock()

    cases = [
        EvaluationCase(
            environment="theEnvironment",
            patient_uuid="thePatientUuid",
            case_type="theType",
            case_group="theGroup",
            case_name="theCaseName",
            description="theDescription",
        ),
        EvaluationCase(
            environment="",
            patient_uuid="",
            case_type="general",
            case_group="common",
            case_name="theCaseName",
            description="",
        ),
    ]
    tested = StoreCases
    with NamedTemporaryFile(delete=True) as temp_file:
        db_path.return_value = Path(temp_file.name)

        # record does not exist yet
        case_db = tested.get("theCaseName")
        assert case_db == cases[1]
        reset_mocks()
        # create record
        tested.upsert(cases[0])
        reset_mocks()
        # retrieve the record
        case_db = tested.get("theCaseName")
        assert case_db == cases[0]
        calls = [call()]
        assert db_path.mock_calls == calls
        reset_mocks()
        # delete record
        tested.delete("theCaseName")
        reset_mocks()
        # retrieve the record
        case_db = tested.get("theCaseName")
        assert case_db == cases[1]
        calls = [call()]
        assert db_path.mock_calls == calls
        reset_mocks()
