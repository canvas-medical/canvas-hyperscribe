from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, call

from evaluations.datastores.postgres.store_results import StoreResults
from evaluations.structures.evaluation_case import EvaluationCase
from evaluations.structures.evaluation_result import EvaluationResult
from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.structures.statistic_end2end import StatisticEnd2End
from evaluations.structures.statistic_test import StatisticTest


def test___init__():
    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    tested = StoreResults(credentials)
    assert tested.credentials == credentials


@patch("evaluations.datastores.postgres.store_results.datetime", wraps=datetime)
@patch("evaluations.datastores.postgres.store_results.connect")
def test_insert(connect, mock_datetime):
    mock_connection = MagicMock()
    mock_cursor = MagicMock()

    def reset_mocks():
        connect.reset_mock()
        mock_datetime.reset_mock()
        mock_connection.reset_mock()
        mock_cursor.reset_mock()

    date_0 = datetime(2025, 3, 26, 11, 38, 21, 123456, tzinfo=timezone.utc)
    mock_datetime.now.side_effect = [date_0]
    connect.return_value.__enter__.side_effect = [mock_connection]
    mock_connection.cursor.return_value.__enter__.side_effect = [mock_cursor]
    mock_cursor.lastrowid = 77

    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    tested = StoreResults(credentials)
    result = tested.insert(
        EvaluationCase(
            environment="theEnvironment",
            patient_uuid="thePatientUuid",
            case_type="theType",
            case_group="theGroup",
            case_name="theCaseName",
            description="theDescription",
        ),
        EvaluationResult(
            run_uuid="theRunUuid",
            commit_uuid="theCommitUuid",
            milliseconds=123456.7,
            passed=False,
            test_file="theTestFile",
            test_name="theTestName",
            test_case="theTestCase",
            errors="theErrors",
        ),
    )
    expected = 77
    assert result == expected
    calls = [
        call(dbname='theDatabase', host='theHost', user='theUser', password='thePassword', port=1234),
        call().__enter__(),
        call().__exit__(None, None, None),
    ]
    assert connect.mock_calls == calls
    calls = [call.now()]
    assert mock_datetime.mock_calls == calls
    calls = [
        call.cursor(),
        call.cursor().__enter__(),
        call.commit(),
        call.cursor().__exit__(None, None, None),
    ]
    assert mock_connection.mock_calls == calls
    calls = [
        call.execute(
            'INSERT INTO "results" ("created","run_uuid","plugin_commit","case_type","case_group","case_name","test_name",'
            '"milliseconds","passed","errors") '
            'VALUES (%(now)s,%(uuid)s,%(commit)s,%(type)s,%(group)s,%(name)s,%(test)s,%(duration)s,%(passed)s,%(errors)s)',
            {
                'now': date_0,
                'uuid': 'theRunUuid',
                'commit': 'theCommitUuid',
                'type': 'theType',
                'group': 'theGroup',
                'name': 'theCaseName',
                'test': 'theTestName',
                'duration': 123456.7,
                'passed': False,
                'errors': 'theErrors',
            }),
    ]
    assert mock_cursor.mock_calls == calls
    reset_mocks()


@patch("evaluations.datastores.postgres.store_results.connect")
def test__select(connect):
    mock_connection = MagicMock()
    mock_cursor = MagicMock()

    def reset_mocks():
        connect.reset_mock()
        mock_connection.reset_mock()
        mock_cursor.reset_mock()

    connect.return_value.__enter__.side_effect = [mock_connection]
    mock_connection.cursor.return_value.__enter__.side_effect = [mock_cursor]
    mock_cursor.description = [
        ["field_1", "meta_1"],
        ["field_2", "meta_2"],
        ["field_3", "meta_3"],
    ]
    mock_cursor.fetchall.side_effect = [
        [
            ["value_1_a", "value_2_a", "value_3_a"],
            ["value_1_b", "value_2_b", "value_3_b"],
        ],
    ]

    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    tested = StoreResults(credentials)
    result = [
        row
        for row in tested._select("theSQL", {"key": "value"})
    ]
    expected = [
        {"field_1": "value_1_a", "field_2": "value_2_a", "field_3": "value_3_a"},
        {"field_1": "value_1_b", "field_2": "value_2_b", "field_3": "value_3_b"},
    ]
    assert result == expected

    calls = [
        call(dbname='theDatabase', host='theHost', user='theUser', password='thePassword', port=1234),
        call().__enter__(),
        call().__exit__(None, None, None),
    ]
    assert connect.mock_calls == calls
    calls = [
        call.cursor(),
        call.cursor().__enter__(),
        call.commit(),
        call.cursor().__exit__(None, None, None),
    ]
    assert mock_connection.mock_calls == calls
    calls = [
        call.execute('theSQL', {'key': 'value'}),
        call.fetchall(),
    ]
    assert mock_cursor.mock_calls == calls
    reset_mocks()


@patch.object(StoreResults, "_select")
def test_statistics_per_test(select):
    def reset_mocks():
        select.reset_mock()

    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    select.side_effect = [
        [
            {"case_name": "caseName1", "test_name": "testName1", "passed_count": 2},
            {"case_name": "caseName2", "test_name": "testName2", "passed_count": 3},
            {"case_name": "caseName3", "test_name": "testName3", "passed_count": 1},
        ]]
    tested = StoreResults(credentials)
    result = tested.statistics_per_test()
    expected = [
        StatisticTest(case_name='caseName1', test_name='testName1', passed_count=2),
        StatisticTest(case_name='caseName2', test_name='testName2', passed_count=3),
        StatisticTest(case_name='caseName3', test_name='testName3', passed_count=1),
    ]
    assert result == expected
    calls = [
        call(
            'SELECT "case_name","test_name",SUM(CASE WHEN "passed"=True THEN 1 ELSE 0 END) AS "passed_count" '
            'FROM "results" '
            'GROUP BY "case_name","test_name"',
            {},
        ),
    ]
    assert select.mock_calls == calls
    reset_mocks()


@patch.object(StoreResults, "_select")
def test_statistics_end2end(select):
    def reset_mocks():
        select.reset_mock()

    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    select.side_effect = [
        [
            {"case_name": "caseName1", "run_count": 2, "end2end": 1},
            {"case_name": "caseName2", "run_count": 3, "end2end": 1},
            {"case_name": "caseName3", "run_count": 1, "end2end": 0},
        ]]
    tested = StoreResults(credentials)
    result = tested.statistics_end2end()
    expected = [
        StatisticEnd2End(case_name='caseName1', run_count=2, end2end=1),
        StatisticEnd2End(case_name='caseName2', run_count=3, end2end=1),
        StatisticEnd2End(case_name='caseName3', run_count=1, end2end=0),
    ]
    assert result == expected
    calls = [
        call(
            'SELECT "case_name",SUM("full_passed") AS "end2end",COUNT(distinct "run_uuid") AS "run_count" '
            'FROM (SELECT  "case_name",  "run_uuid",  '
            '(CASE WHEN SUM(CASE WHEN "passed"=True THEN 1 ELSE 0 END)=COUNT(1) THEN 1 ELSE 0 END) AS "full_passed"  '
            'FROM "results"  '
            'GROUP BY "case_name","run_uuid") '
            'GROUP BY "case_name"',
            {},
        ),
    ]
    assert select.mock_calls == calls
    reset_mocks()
