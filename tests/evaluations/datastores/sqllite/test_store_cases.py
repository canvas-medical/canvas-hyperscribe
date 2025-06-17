from datetime import datetime, timezone, UTC
from pathlib import Path
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
                "`limited_cache` TEXT NOT NULL,"
                "`case_type` TEXT NOT NULL,"
                "`case_group` TEXT NOT NULL,"
                "`case_name` TEXT NOT NULL,"
                "`cycles` INT NOT NULL,"
                "`description` TEXT NOT NULL)")
    assert result == expected


def test__update_sql():
    tested = StoreCases
    result = tested._update_sql()
    expected = ("UPDATE `cases` "
                "SET `updated`=:now,`environment`=:environment,`patient_uuid`=:patient,`limited_cache`=:cache,"
                "`case_type`=:type,`case_group`=:group,`cycles`=:cycles,`description`=:description "
                "WHERE `case_name`=:name")
    assert result == expected


def test__insert_sql():
    tested = StoreCases
    result = tested._insert_sql()
    expected = (
        "INSERT INTO `cases` (`created`,`updated`,`environment`,`patient_uuid`,`limited_cache`,`case_type`,`case_group`,`case_name`,`cycles`,`description`) "
        "VALUES (:now,:now,:environment,:patient,:cache,:type,:group,:name,:cycles,:description)")
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
        limited_cache={"key": "theLimitedCache"},
        case_type="theType",
        case_group="theGroup",
        case_name="theCaseName",
        cycles=3,
        description="theDescription",
    ))
    calls = [call.now(UTC)]
    assert mock_datetime.mock_calls == calls
    calls = [call({
        "now": date_0,
        "environment": "theEnvironment",
        "patient": "thePatientUuid",
        "cache": {"key": "theLimitedCache"},
        "type": "theType",
        "group": "theGroup",
        "description": "theDescription",
        "name": "theCaseName",
        "cycles": 3,
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


@patch.object(StoreCases, "_select")
def test_get(select):
    def reset_mocks():
        select.reset_mock()

    calls = [
        call("SELECT `environment`,`patient_uuid`,`limited_cache`,`case_type`,`case_group`,`case_name`,`cycles`,`description` "
             "FROM `cases` "
             "WHERE `case_name`=:name",
             {'name': 'theCaseName'})
    ]

    tested = StoreCases
    # no record matching the case name
    select.side_effect = [[]]
    result = tested.get("theCaseName")
    expected = EvaluationCase(
        environment="",
        patient_uuid="",
        limited_cache={},
        case_type="general",
        case_group="common",
        case_name="theCaseName",
        cycles=0,
        description="",
    )
    assert result == expected
    assert select.mock_calls == calls
    reset_mocks()

    # record matching the case name
    select.side_effect = [[{
        "environment": "theEnvironment",
        "patient_uuid": "thePatientUuid",
        "limited_cache": {"key": "theLimitedCache"},
        "case_type": "theType",
        "case_group": "theGroup",
        "case_name": "theCaseName",
        "cycles": 3,
        "description": "theDescription",
    }]]
    result = tested.get("theCaseName")
    expected = EvaluationCase(
        environment="theEnvironment",
        patient_uuid="thePatientUuid",
        limited_cache={"key": "theLimitedCache"},
        case_type="theType",
        case_group="theGroup",
        case_name="theCaseName",
        cycles=3,
        description="theDescription",
    )
    assert result == expected
    assert select.mock_calls == calls
    reset_mocks()


@patch.object(StoreCases, "_select")
def test_all(select):
    def reset_mocks():
        select.reset_mock()

    calls = [
        call("SELECT `environment`,`patient_uuid`,`case_type`,`case_group`,`case_name`,`cycles`,`description` "
             "FROM `cases` "
             "ORDER BY 3",
             {})
    ]

    tested = StoreCases
    # no record matching the case name
    select.side_effect = [[]]
    result = tested.all()
    assert result == []
    assert select.mock_calls == calls
    reset_mocks()

    # record matching the case name
    select.side_effect = [[
        {
            "environment": "theEnvironment1",
            "patient_uuid": "thePatientUuid1",
            "case_type": "theType1",
            "case_group": "theGroup1",
            "case_name": "theCaseName1",
            "cycles": 2,
            "description": "theDescription1",
        },
        {
            "environment": "theEnvironment2",
            "patient_uuid": "thePatientUuid2",
            "case_type": "theType2",
            "case_group": "theGroup2",
            "case_name": "theCaseName2",
            "cycles": 3,
            "description": "theDescription2",
        },
        {
            "environment": "theEnvironment3",
            "patient_uuid": "thePatientUuid3",
            "case_type": "theType3",
            "case_group": "theGroup3",
            "case_name": "theCaseName3",
            "cycles": 7,
            "description": "theDescription3",
        },
    ]]
    result = tested.all()
    expected = [
        EvaluationCase(
            environment="theEnvironment1",
            patient_uuid="thePatientUuid1",
            case_type="theType1",
            case_group="theGroup1",
            case_name="theCaseName1",
            cycles=2,
            description="theDescription1",
        ),
        EvaluationCase(
            environment="theEnvironment2",
            patient_uuid="thePatientUuid2",
            case_type="theType2",
            case_group="theGroup2",
            case_name="theCaseName2",
            cycles=3,
            description="theDescription2",
        ),
        EvaluationCase(
            environment="theEnvironment3",
            patient_uuid="thePatientUuid3",
            case_type="theType3",
            case_group="theGroup3",
            case_name="theCaseName3",
            cycles=7,
            description="theDescription3",
        ),
    ]
    assert result == expected
    assert select.mock_calls == calls
    reset_mocks()
