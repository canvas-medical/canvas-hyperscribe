from datetime import datetime, timezone, UTC
from unittest.mock import patch, call

from evaluations.datastores.postgres.postgres import Postgres
from evaluations.datastores.postgres.store_results import StoreResults
from evaluations.structures.evaluation_case import EvaluationCase
from evaluations.structures.evaluation_result import EvaluationResult
from evaluations.structures.postgres_credentials import PostgresCredentials
from evaluations.structures.statistic_end2end import StatisticEnd2End
from evaluations.structures.statistic_test import StatisticTest
from tests.helper import compare_sql


def helper_instance() -> StoreResults:
    credentials = PostgresCredentials(
        database="theDatabase",
        user="theUser",
        password="thePassword",
        host="theHost",
        port=1234,
    )
    return StoreResults(credentials)


def test_class():
    assert issubclass(StoreResults, Postgres)


@patch("evaluations.datastores.postgres.store_results.datetime", wraps=datetime)
@patch.object(StoreResults, "_alter")
def test_insert(alter, mock_datetime):
    def reset_mocks():
        alter.reset_mock()
        mock_datetime.reset_mock()

    date_0 = datetime(2025, 3, 26, 11, 38, 21, 123456, tzinfo=timezone.utc)
    mock_datetime.now.side_effect = [date_0]

    tested = helper_instance()
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
    assert len(alter.mock_calls) == 1
    sql, params, involved_id = alter.mock_calls[0].args
    exp_sql = (
        'INSERT INTO "results" ("created", "run_uuid", "plugin_commit", "case_type", "case_group", "case_name",'
        ' "cycles", "cycle", "test_name", "milliseconds", "passed", "errors") '
        "VALUES (%(now)s, %(uuid)s, %(commit)s, %(type)s, %(group)s, %(name)s,"
        " %(cycles)s, %(cycle)s, %(test)s, %(duration)s, %(passed)s, %(errors)s)"
    )
    assert compare_sql(sql, exp_sql)
    exp_params = {
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
    }
    assert params == exp_params
    assert involved_id is None
    reset_mocks()


@patch.object(StoreResults, "_select")
def test_statistics_per_test(select):
    def reset_mocks():
        select.reset_mock()

    select.side_effect = [
        [
            {"case_name": "caseName1", "test_name": "testName1", "passed_count": 2},
            {"case_name": "caseName2", "test_name": "testName2", "passed_count": 3},
            {"case_name": "caseName3", "test_name": "testName3", "passed_count": 1},
        ],
    ]
    tested = helper_instance()
    result = tested.statistics_per_test()
    expected = [
        StatisticTest(case_name="caseName1", test_name="testName1", passed_count=2),
        StatisticTest(case_name="caseName2", test_name="testName2", passed_count=3),
        StatisticTest(case_name="caseName3", test_name="testName3", passed_count=1),
    ]
    assert result == expected

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    exp_sql = (
        'SELECT "case_name", "test_name",'
        ' SUM(CASE WHEN "passed" = True THEN 1 ELSE 0 END) / "cycles" AS "passed_count" '
        'FROM "results" '
        'WHERE "cycles" > 0 '
        'GROUP BY "case_name", "test_name", "cycles" '
        "ORDER BY 1, 2"
    )
    assert compare_sql(sql, exp_sql)
    assert params == {}
    reset_mocks()


@patch.object(StoreResults, "_select")
def test_statistics_end2end(select):
    def reset_mocks():
        select.reset_mock()

    select.side_effect = [
        [
            {"case_name": "caseName1", "run_count": 2, "full_run": 1, "end2end": 1},
            {"case_name": "caseName2", "run_count": 3, "full_run": 1, "end2end": 1},
            {"case_name": "caseName3", "run_count": 1, "full_run": 0, "end2end": 0},
        ],
    ]
    tested = helper_instance()
    result = tested.statistics_end2end()
    expected = [
        StatisticEnd2End(case_name="caseName1", run_count=2, full_run=1, end2end=1),
        StatisticEnd2End(case_name="caseName2", run_count=3, full_run=1, end2end=1),
        StatisticEnd2End(case_name="caseName3", run_count=1, full_run=0, end2end=0),
    ]
    assert result == expected

    assert len(select.mock_calls) == 1
    sql, params = select.mock_calls[0].args
    exp_sql = (
        'SELECT "case_name", SUM("full_run") AS "full_run", SUM("full_passed") AS "end2end", '
        'COUNT(distinct "run_uuid") AS "run_count" '
        'FROM (SELECT "case_name", "run_uuid",'
        ' (CASE WHEN SUM(CASE WHEN "passed" = True THEN 1 ELSE 0 END) = COUNT(1) THEN 1 ELSE 0 END) AS "full_passed",'
        ' (CASE WHEN MAX("cycle") = -1 THEN 1 ELSE 0 END) AS "full_run" '
        'FROM "results" GROUP BY "case_name", "run_uuid") '
        'GROUP BY "case_name" ORDER BY 1'
    )
    assert compare_sql(sql, exp_sql)
    assert params == {}
    reset_mocks()
