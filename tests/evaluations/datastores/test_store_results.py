import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import patch, call

from evaluations.datastores.store_cases import StoreCases
from evaluations.datastores.store_results import StoreResults
from evaluations.structures.evaluation_case import EvaluationCase
from evaluations.structures.evaluation_result import EvaluationResult
from evaluations.structures.statistic_case_test import StatisticCaseTest


def test__create_table_sql():
    tested = StoreResults
    result = tested._create_table_sql()
    expected = ("CREATE TABLE IF NOT EXISTS results ("
                "`id` INTEGER PRIMARY KEY AUTOINCREMENT,"
                "`created` DATETIME NOT NULL,"
                "`run_uuid` TEXT NOT NULL,"
                "`plugin_commit` TEXT NOT NULL,"
                "`case_type` TEXT NOT NULL,"
                "`case_group` TEXT NOT NULL,"
                "`case_name` TEXT NOT NULL,"
                "`test_name` TEXT NOT NULL,"
                "`milliseconds` REAL NOT NULL,"
                "`passed` INTEGER NOT NULL,"
                "`errors` TEXT NOT NULL)")
    assert result == expected


def test__insert_sql():
    tested = StoreResults
    result = tested._insert_sql()
    expected = ("INSERT INTO results (`created`,`run_uuid`,`plugin_commit`,`case_type`,`case_group`,`case_name`,"
                "`test_name`,`milliseconds`,`passed`,`errors`) "
                "VALUES (:now,:uuid,:commit,:type,:group,:name,:test,:duration,:passed,:errors)")
    assert result == expected


def test__db_path():
    tested = StoreResults
    with patch('evaluations.datastores.store_results.Path') as mock_path:
        mock_path.side_effect = [Path('/a/b/c/d/e/f/g/theFile.py')]
        result = tested._db_path()
        assert result == Path('/a/b/c/d/evaluation_results.db')


@patch("evaluations.datastores.store_results.datetime", wraps=datetime)
@patch.object(StoreCases, "get")
@patch.object(StoreResults, "_db_path")
def test_insert(db_path, case_get, mock_datetime):
    def reset_mocks():
        db_path.reset_mock()
        case_get.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 3, 26, 11, 38, 21, 123456, tzinfo=timezone.utc)

    tested = StoreResults
    with NamedTemporaryFile(delete=True) as temp_file:
        db_path.return_value = Path(temp_file.name)
        case_get.side_effect = [
            EvaluationCase(
                environment="theEnvironment",
                patient_uuid="thePatientUuid",
                case_type="theType",
                case_group="theGroup",
                case_name="theCaseName",
                description="theDescription",
            )
        ]
        mock_datetime.now.side_effect = [date_0]
        result = EvaluationResult(
            test_file="theTestFile",
            test_case="theTestCase",
            test_name="theTestName",
            milliseconds=123456.7,
            passed=False,
            errors="theErrors",
        )
        tested.insert("theRunUuid", "theCommit", result)

        calls = [call()]
        assert db_path.mock_calls == calls
        calls = [call('theTestCase')]
        assert case_get.mock_calls == calls
        calls = [call.now()]
        assert mock_datetime.mock_calls == calls
        reset_mocks()

        with sqlite3.connect(temp_file.name) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM `results`")
            result = [
                {
                    "id": r["id"],
                    "created": r["created"],
                    "run_uuid": r["run_uuid"],
                    "plugin_commit": r["plugin_commit"],
                    "case_type": r["case_type"],
                    "case_group": r["case_group"],
                    "case_name": r["case_name"],
                    "test_name": r["test_name"],
                    "milliseconds": r["milliseconds"],
                    "passed": r["passed"],
                    "errors": r["errors"],
                }
                for r in cursor.fetchall()
            ]
            expected = [
                {
                    'id': 1,
                    'created': '2025-03-26 11:38:21.123456+00:00',
                    'run_uuid': 'theRunUuid',
                    'plugin_commit': 'theCommit',
                    'case_type': 'theType',
                    'case_group': 'theGroup',
                    'case_name': 'theCaseName',
                    'test_name': 'theTestName',
                    'milliseconds': 123456.7,
                    'passed': 0,
                    'errors': 'theErrors',
                },
            ]
            assert result == expected


@patch.object(StoreResults, "_db_path")
def test_case_test_statistics(db_path):
    def reset_mocks():
        db_path.reset_mock()

    tested = StoreResults
    with NamedTemporaryFile(delete=True) as temp_file:
        db_path.return_value = Path(temp_file.name)
        # no records
        result = tested.case_test_statistics()
        assert result == []

        calls = [call()]
        assert db_path.mock_calls == calls
        reset_mocks()

        # with records
        date_0 = datetime(2025, 3, 26, 11, 38, 21, 123456, tzinfo=timezone.utc)
        records = [
            # all pass with 4 tests
            {
                "now": date_0,
                "uuid": "uuid1",
                "commit": "commit1",
                "type": "theType",
                "group": "theGroup",
                "name": "theCase1",
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
                "test": "theTest",
                "duration": 1253.0,
                "passed": 1,
                "errors": "",
            },
        ]
        with sqlite3.connect(temp_file.name) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(tested._create_table_sql())
            for parameter in records:
                cursor.execute(tested._insert_sql(), parameter)
            conn.commit()

        result = tested.case_test_statistics()
        expected = [
            StatisticCaseTest(
                case_name='theCase1',
                run_count=2,
                audio2transcript=1,
                transcript2instructions=2,
                instruction2parameters=2,
                parameters2command=1,
                end2end=2,
            ),
            StatisticCaseTest(
                case_name='theCase2',
                run_count=1,
                audio2transcript=-1,
                transcript2instructions=1,
                instruction2parameters=0,
                parameters2command=1,
                end2end=0,
            ),
            StatisticCaseTest(
                case_name='theCase3',
                run_count=1,
                audio2transcript=-1,
                transcript2instructions=-1,
                instruction2parameters=-1,
                parameters2command=-1,
                end2end=1,
            ),
        ]
        assert result == expected

        calls = [call()]
        assert db_path.mock_calls == calls
        reset_mocks()
