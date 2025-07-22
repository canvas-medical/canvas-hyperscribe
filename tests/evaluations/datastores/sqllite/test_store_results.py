from datetime import datetime, timezone, UTC
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import patch, call

from evaluations.datastores.sqllite.store_results import StoreResults
from evaluations.structures.evaluation_case import EvaluationCase
from evaluations.structures.evaluation_result import EvaluationResult
from evaluations.structures.statistic_end2end import StatisticEnd2End
from evaluations.structures.statistic_test import StatisticTest


def test__create_table_sql():
    tested = StoreResults
    result = tested._create_table_sql()
    expected = (
        "CREATE TABLE IF NOT EXISTS results ("
        "`id` INTEGER PRIMARY KEY AUTOINCREMENT,"
        "`created` DATETIME NOT NULL,"
        "`run_uuid` TEXT NOT NULL,"
        "`plugin_commit` TEXT NOT NULL,"
        "`case_type` TEXT NOT NULL,"
        "`case_group` TEXT NOT NULL,"
        "`case_name` TEXT NOT NULL,"
        "`cycles` INT NOT NULL,"
        "`cycle` INT NOT NULL,"
        "`test_name` TEXT NOT NULL,"
        "`milliseconds` REAL NOT NULL,"
        "`passed` INTEGER NOT NULL,"
        "`errors` TEXT NOT NULL)"
    )
    assert result == expected


def test__insert_sql():
    tested = StoreResults
    result = tested._insert_sql()
    expected = (
        "INSERT INTO results (`created`,`run_uuid`,`plugin_commit`,`case_type`,`case_group`,`case_name`,"
        "`cycles`,`cycle`,`test_name`,`milliseconds`,`passed`,`errors`) "
        "VALUES (:now,:uuid,:commit,:type,:group,:name,:cycles,:cycle,:test,:duration,:passed,:errors)"
    )
    assert result == expected


def test__db_path():
    tested = StoreResults
    with patch("evaluations.datastores.sqllite.store_results.Path") as mock_path:
        mock_path.side_effect = [Path("/a/b/c/d/e/f/g/theFile.py")]
        result = tested._db_path()
        assert result == Path("/a/b/c/evaluation_results.db")


@patch("evaluations.datastores.sqllite.store_results.datetime", wraps=datetime)
@patch.object(StoreResults, "_insert")
def test_insert(insert, mock_datetime):
    def reset_mocks():
        insert.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 3, 26, 11, 38, 21, 123456, tzinfo=timezone.utc)
    tested = StoreResults
    mock_datetime.now.side_effect = [date_0]
    tested.insert(
        EvaluationCase(
            environment="theEnvironment",
            patient_uuid="thePatientUuid",
            case_type="theType",
            case_group="theGroup",
            case_name="theCaseName",
            cycles=9,
            description="theDescription",
        ),
        EvaluationResult(
            run_uuid="theRunUuid",
            commit_uuid="theCommitUuid",
            milliseconds=123456.7,
            passed=False,
            test_file="theTestFile",
            test_name="theTestName",
            case_name="theTestCase",
            cycle=7,
            errors="theErrors",
        ),
    )
    calls = [call.now(UTC)]
    assert mock_datetime.mock_calls == calls
    calls = [
        call(
            {
                "now": date_0,
                "uuid": "theRunUuid",
                "commit": "theCommitUuid",
                "type": "theType",
                "group": "theGroup",
                "name": "theCaseName",
                "cycles": 9,
                "cycle": 7,
                "test": "theTestName",
                "duration": 123456.7,
                "passed": False,
                "errors": "theErrors",
            },
        ),
    ]
    assert insert.mock_calls == calls
    reset_mocks()


@patch.object(StoreResults, "_db_path")
def test_statistics_per_test(db_path):
    def reset_mocks():
        db_path.reset_mock()

    tested = StoreResults
    with NamedTemporaryFile(delete=True) as temp_file:
        db_path.return_value = Path(temp_file.name)
        # no records
        result = tested.statistics_per_test()
        assert result == []

        calls = [call()]
        assert db_path.mock_calls == calls
        reset_mocks()

        # with records
        records = helper_records()
        for parameter in records:
            tested._insert(parameter)
        reset_mocks()

        result = tested.statistics_per_test()
        expected = [
            StatisticTest(case_name="theCase1", test_name="audio2transcript", passed_count=0),
            StatisticTest(case_name="theCase1", test_name="instruction2parameters", passed_count=1),
            StatisticTest(case_name="theCase1", test_name="parameters2command", passed_count=0),
            StatisticTest(case_name="theCase1", test_name="transcript2instructions", passed_count=1),
            StatisticTest(case_name="theCase2", test_name="instruction2parameters", passed_count=0),
            StatisticTest(case_name="theCase2", test_name="parameters2command", passed_count=0),
            StatisticTest(case_name="theCase2", test_name="transcript2instructions", passed_count=0),
            StatisticTest(case_name="theCase3", test_name="theTest", passed_count=0),
        ]
        assert result == expected

        calls = [call()]
        assert db_path.mock_calls == calls
        reset_mocks()


@patch.object(StoreResults, "_db_path")
def test_statistics_end2end(db_path):
    def reset_mocks():
        db_path.reset_mock()

    tested = StoreResults
    with NamedTemporaryFile(delete=True) as temp_file:
        db_path.return_value = Path(temp_file.name)
        # no records
        result = tested.statistics_end2end()
        assert result == []

        calls = [call()]
        assert db_path.mock_calls == calls
        reset_mocks()

        # with records
        records = helper_records()
        for parameter in records:
            tested._insert(parameter)
        reset_mocks()

        result = tested.statistics_end2end()
        expected = [
            StatisticEnd2End(case_name="theCase1", run_count=2, full_run=0, end2end=2),
            StatisticEnd2End(case_name="theCase2", run_count=1, full_run=0, end2end=0),
            StatisticEnd2End(case_name="theCase3", run_count=1, full_run=0, end2end=1),
        ]
        assert result == expected

        calls = [call()]
        assert db_path.mock_calls == calls
        reset_mocks()


def helper_records() -> list[dict]:
    date_0 = datetime(2025, 3, 26, 11, 38, 21, 123456, tzinfo=timezone.utc)
    return [
        # all pass with 4 tests
        {
            "now": date_0,
            "uuid": "uuid1",
            "commit": "commit1",
            "type": "theType",
            "group": "theGroup",
            "name": "theCase1",
            "cycles": 2,
            "cycle": 1,
            "test": "audio2transcript",
            "duration": 1253.0,
            "passed": 1,
            "errors": "",
        },
        {
            "now": date_0,
            "uuid": "uuid1",
            "commit": "commit1",
            "type": "theType",
            "group": "theGroup",
            "name": "theCase1",
            "cycles": 2,
            "cycle": 1,
            "test": "transcript2instructions",
            "duration": 1253.0,
            "passed": 1,
            "errors": "",
        },
        {
            "now": date_0,
            "uuid": "uuid1",
            "commit": "commit1",
            "type": "theType",
            "group": "theGroup",
            "name": "theCase1",
            "cycles": 2,
            "cycle": 1,
            "test": "instruction2parameters",
            "duration": 1253.0,
            "passed": 1,
            "errors": "",
        },
        {
            "now": date_0,
            "uuid": "uuid1",
            "commit": "commit1",
            "type": "theType",
            "group": "theGroup",
            "name": "theCase1",
            "cycles": 2,
            "cycle": 1,
            "test": "parameters2command",
            "duration": 1253.0,
            "passed": 1,
            "errors": "",
        },
        # all pass with 2 tests
        {
            "now": date_0,
            "uuid": "uuid2",
            "commit": "commit1",
            "type": "theType",
            "group": "theGroup",
            "name": "theCase1",
            "cycles": 2,
            "cycle": 1,
            "test": "transcript2instructions",
            "duration": 1253.0,
            "passed": 1,
            "errors": "",
        },
        {
            "now": date_0,
            "uuid": "uuid2",
            "commit": "commit1",
            "type": "theType",
            "group": "theGroup",
            "name": "theCase1",
            "cycles": 2,
            "cycle": 1,
            "test": "instruction2parameters",
            "duration": 1253.0,
            "passed": 1,
            "errors": "",
        },
        # one failed with 3 tests
        {
            "now": date_0,
            "uuid": "uuid3",
            "commit": "commit3",
            "type": "theType",
            "group": "theGroup",
            "name": "theCase2",
            "cycles": 2,
            "cycle": 1,
            "test": "transcript2instructions",
            "duration": 1253.0,
            "passed": 1,
            "errors": "",
        },
        {
            "now": date_0,
            "uuid": "uuid3",
            "commit": "commit3",
            "type": "theType",
            "group": "theGroup",
            "name": "theCase2",
            "cycles": 2,
            "cycle": 1,
            "test": "instruction2parameters",
            "duration": 1253.0,
            "passed": 0,
            "errors": "",
        },
        {
            "now": date_0,
            "uuid": "uuid3",
            "commit": "commit3",
            "type": "theType",
            "group": "theGroup",
            "name": "theCase2",
            "cycles": 2,
            "cycle": 1,
            "test": "parameters2command",
            "duration": 1253.0,
            "passed": 1,
            "errors": "",
        },
        # pass but unknown test
        {
            "now": date_0,
            "uuid": "uuid4",
            "commit": "commit3",
            "type": "theType",
            "group": "theGroup",
            "name": "theCase3",
            "cycles": 2,
            "cycle": 1,
            "test": "theTest",
            "duration": 1253.0,
            "passed": 1,
            "errors": "",
        },
    ]
