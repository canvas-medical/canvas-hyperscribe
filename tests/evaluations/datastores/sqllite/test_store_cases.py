from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import patch, call

from evaluations.datastores.sqllite.store_cases import StoreCases
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
    with patch('evaluations.datastores.sqllite.store_cases.Path') as mock_path:
        mock_path.side_effect = [Path('/a/b/c/d/e/f/g/theFile.py')]
        result = tested._db_path()
        assert result == Path('/a/b/c/d/e/evaluation_cases.db')


@patch("evaluations.datastores.sqllite.store_cases.datetime", wraps=datetime)
@patch.object(StoreCases, "_upsert")
def test_upsert(upsert, mock_datetime):
    def reset_mocks():
        upsert.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 3, 26, 11, 38, 21, 123456, tzinfo=timezone.utc)
    tested = StoreCases
    mock_datetime.now.side_effect = [date_0]
    tested.upsert(EvaluationCase(
        environment="theEnvironment",
        patient_uuid="thePatientUuid",
        case_type="theType",
        case_group="theGroup",
        case_name="theCaseName",
        description="theDescription",
    ))
    calls = [call.now()]
    assert mock_datetime.mock_calls == calls
    calls = [call({
        "now": date_0,
        "environment": "theEnvironment",
        "patient": "thePatientUuid",
        "type": "theType",
        "group": "theGroup",
        "description": "theDescription",
        "name": "theCaseName",
    })]
    assert upsert.mock_calls == calls
    reset_mocks()


@patch.object(StoreCases, "_delete")
def test_delete(delete):
    def reset_mocks():
        delete.reset_mock()

    tested = StoreCases
    tested.delete("theCaseName")
    calls = [call({"name": "theCaseName"})]
    assert delete.mock_calls == calls
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
